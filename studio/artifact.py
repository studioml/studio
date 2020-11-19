import hashlib
import os
import re

import tarfile
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

from . import fs_tracker, util, logs
from . import model_setup
from .storage_type import StorageType
from .storage_handler import StorageHandler
from .storage_util import tar_artifact, untar_artifact

# The purpose of this class is to encapsulate the logic
# of handling artifact's state and it's transition between
# being local on client's side, cached in shared storage location,
# downloaded into payload execution environment etc.
# Part of artifact is a reference to StorageHandler instance,
# potentially unique for each Artifact instance.
# This StorageHandler defines where artifact is currently stored
# and how it is accessed.
class Artifact:

    def __init__(self, art_name, art_dict, logger=None):
        self.name = art_name
        self.key: str = None
        self.local_path: str = None
        self.remote_path: str = None
        self.credentials = None
        self.hash = None

        self.logger = logger
        if self.logger is None:
            self.logger = logs.getLogger(self.__class__.__name__)
            self.logger.setLevel(model_setup.get_model_verbose_level())

        self.storage_handler: StorageHandler = None
        self.compression: str = None

        artifact_store = model_setup.get_model_artifact_store()
        self.storage_handler =\
            artifact_store.get_storage_handler() if artifact_store else None
        self.unpack: bool = art_dict.get('unpack')
        self.is_mutable: bool = art_dict.get('mutable')
        if 'key' in art_dict.keys():
            self.key = art_dict['key']
        if 'local' in art_dict.keys():
            self.local_path = art_dict['local']
        if 'qualified' in art_dict.keys():
            self.remote_path = art_dict['qualified']
        if 'url' in art_dict.keys():
            self.remote_path = art_dict['url']
        if 'hash' in art_dict.keys():
            self.hash = art_dict['hash']

    def upload(self, local_path=None):
        if self.storage_handler is None:
            msg: str = "No storage handler is set for artifact {0}"\
                .format(self.key)
            util.report_fatal(msg, self.logger)

        if local_path is None:
            local_path = self.local_path

        if self.in_blobstore:
            self.logger.debug(('Artifact with key {0} exists in blobstore, ' +
                              'skipping the upload').format(self.key))
            return self.key

        if os.path.exists(local_path):
            tar_filename =\
                tar_artifact(local_path, self.key,
                             self.compression, self.logger)
            if self.key is None:
                self.key = 'blobstore/' + util.sha256_checksum(tar_filename) \
                      + '.tar' + util.compression_to_extension(self.compression)
                time_stamp = self.storage_handler.get_file_timestamp(self.key)
                if time_stamp is not None:
                    self.logger.debug(
                        ('Artifact with key {0} exists in blobstore, ' +
                         'skipping the upload').format(self.key))
                    os.remove(tar_filename)
                    return self.key

            self.storage_handler.upload_file(self.key, tar_filename)
            os.remove(tar_filename)
            return self.key
        else:
            self.logger.debug(("Local path {0} does not exist. " +
                               "Not uploading anything.")
                              .format(local_path))
            return None

    def download(self, local_path=None, only_newer=True):
        if self.storage_handler is None:
            msg: str = "No storage handler is set for artifact {0}"\
                .format(self.key)
            util.report_fatal(msg, self.logger)

        timestamp_shift = self.storage_handler.get_timestamp_shift()

        if self.key is None:
            if self.is_mutable:
                self.logger.info("Downloading mutable artifact: {0}"
                                  .format(self.name))
            if self.remote_path is None:
                self.logger.error(
                    "CANNOT download artifact without remote path: {0}"
                        .format(self.name))
                assert(False)

            key = self._generate_key()
            local_path = fs_tracker.get_blob_cache(key)
            if os.path.exists(local_path):
                self.logger.debug(('Immutable artifact exists at local_path {0},' +
                                   ' skipping the download').format(local_path))
                self.local_path = local_path
                return local_path

            if self.storage_handler.type == StorageType.storageDockerHub or \
               self.storage_handler.type == StorageType.storageSHub:
                self.logger.debug(
                        'Qualified {0} points to a shub or dockerhub,' +
                        ' skipping the download'.format(self.remote_path))
                return self.remote_path

            self.storage_handler.download_file(
                self.remote_path, local_path)

            self.logger.debug('Downloaded file {0} from external source {1}'
                              .format(local_path, self.remote_path))
            self.local_path = local_path
            return self.local_path

        if local_path is None:
            if self.local_path is not None and \
                os.path.exists(self.local_path):
                local_path = self.local_path
            else:
                if self.is_mutable:
                    local_path = fs_tracker.get_artifact_cache(self.key)
                else:
                    local_path = fs_tracker.get_blob_cache(self.key)
                    if os.path.exists(local_path):
                        self.logger.debug('Immutable artifact exists at local_path {0},' +
                                          ' skipping the download').format(local_path)
                        self.local_path = local_path
                        return local_path

        local_path = re.sub('\/\Z', '', local_path)
        self.logger.debug("Downloading dir {0} to local path {1} from storage..."
                          .format(self.key, local_path))

        if only_newer and os.path.exists(local_path):
            self.logger.debug(
                'Comparing date of the artifact {0} in storage with local {1}'
                    .format(self.key, local_path))
            storage_time = self.storage_handler.get_file_timestamp(self.key)
            local_time = os.path.getmtime(local_path)
            if storage_time is None:
                msg: str = \
                    "Unable to get storage timestamp for {0}, storage is either " + \
                    "corrupted or has not finished uploading".format(self.key)
                util.report_fatal(msg)
                return local_path

            if local_time > storage_time - timestamp_shift:
                self.logger.debug(
                    "Local path {0} is younger than stored {1}, skipping the download"
                        .format(local_path, self.key))
                return local_path

        tar_filename = util.get_temp_filename()
        self.logger.debug("tar_filename = {0} ".format(tar_filename))

        # Now download our artifact from storage and untar it:
        try:
            result: bool =\
                self.storage_handler.download_file(self.key, tar_filename)
            # TODO: why we do this here? local_path is bogus
            # if download failed.
            if not result:
                return local_path
        except BaseException as exc:
            msg: str = \
                "FAILED to download {0}: {1}. ABORTING.".format(self.key, exc)
            util.report_fatal(msg, self.logger)

        if os.path.exists(tar_filename):
            untar_artifact(local_path, tar_filename, self.logger)
            os.remove(tar_filename)
        else:
            util.report_fatal('file {0} download failed'
                              .format(tar_filename), self.logger)
        self.local_path = local_path
        return local_path

    def delete(self):
        if self.key is not None:
            self.logger.debug('Deleting artifact: {0}'.format(self.key))
            self.storage_handler.delete_file(self.key)


    def get_url(self, method='GET', get_timestamp=False):
        if self.key is not None:
            url = self.storage_handler.get_file_url(self.key, method=method)
        elif self.storage_handler.type == StorageType.storageHTTP:
            url = self.remote_path
        else:
            url = None

        if get_timestamp:
            timestamp = self.storage_handler.get_file_timestamp(self.key)
            return url, timestamp
        else:
            return url

        return None


    def stream(self):
        url = self.get_url()
        if url is None:
            return None

        fileobj = urlopen(url)
        if fileobj:
            try:
                retval = tarfile.open(fileobj=fileobj, mode='r|*')
                return retval
            except BaseException as exc:
                fileobj.close()
                msg: str = 'FAILED to stream artifact {0}: {1}'.format(url, exc)
                util.report_fatal(msg, self.logger)
        return None


    def get_hash(self, local_path=None):

        if local_path is None:
            local_path = self.local_path

        if local_path is None or not os.path.exists(local_path):
            return self._generate_key()

        tar_filename =\
            tar_artifact(local_path, self.key, self.compression, self.logger)

        try:
            retval = util.sha256_checksum(tar_filename)
            os.remove(tar_filename)
            self.logger.debug(
                'deleted local artifact file {0}'.format(tar_filename))
            return retval
        except BaseException as exc:
            self.logger.error(
                'error generating a hash for {0}: {1}'
                    .format(tar_filename, repr(exc)))
        return None


    def _setup_storage_handler(self):
        raise NotImplementedError("_setup_storage_handler")


    def to_dict(self):
        result = dict()
        result['unpack'] = self.unpack
        result['mutable'] = self.is_mutable
        if self.key is not None:
            result['key'] = self.key
        if self.local_path is not None:
            result['local'] = self.local_path
        if self.remote_path is not None:
            if self.storage_handler.type == StorageType.storageHTTP:
                result['url'] = self.remote_path
            else:
                result['qualified'] = self.remote_path

        if self.storage_handler.type == StorageType.storageS3:
            # Get artifact bucket directly from remote_path:
            _, bucket, _ = util.parse_s3_path(self.remote_path)
            result['bucket'] = bucket

        return result


    @property
    def in_blobstore(self) -> bool:
        if self.key is not None and self.key.startswith('blobstore/') and \
           self.storage_handler.get_file_timestamp(self.key) is not None:
            return True
        return False

    def _generate_key(self):
        return hashlib.sha256(self.remote_path.encode()).hexdigest()



