import hashlib
import os
import re

import tarfile
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen
from typing import Dict

from studio.artifacts import artifacts_tracker
from studio.util import util, logs
from studio.credentials import credentials
from studio.storage import storage_setup
from studio.storage.storage_type import StorageType
from studio.storage.storage_handler import StorageHandler
from studio.storage.storage_handler_factory import StorageHandlerFactory
from studio.storage.storage_util import tar_artifact, untar_artifact

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
            self.logger = logs.get_logger(self.__class__.__name__)
            self.logger.setLevel(storage_setup.get_storage_verbose_level())

        self.storage_handler: StorageHandler = None

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
        self.credentials = credentials.Credentials.get_credentials(art_dict)

        self._setup_storage_handler(art_dict)

    def upload(self, local_path=None):
        if self.storage_handler is None:
            msg: str = "No storage handler is set for artifact {0}"\
                .format(self.key)
            util.report_fatal(msg, self.logger)

        if local_path is None:
            local_path = self.local_path

        if self.in_blobstore:
            msg: str = ('Artifact with key {0} exists in blobstore, ' +
                        'skipping the upload').format(self.key)
            self.logger.debug(msg)
            return self.key

        if os.path.exists(local_path):
            tar_filename =\
                tar_artifact(local_path, self.key,
                             self.get_compression(), self.logger)
            if self.key is None:
                self.key = 'blobstore/' + util.sha256_checksum(tar_filename) \
                      + '.tar' + util.compression_to_extension(self.get_compression())
                time_stamp = self.storage_handler.get_file_timestamp(self.key)
                if time_stamp is not None:
                    self.logger.debug(
                        'Artifact with key %s exists in blobstore, skipping the upload',
                        self.key)
                    os.remove(tar_filename)
                    return self.key

            self.storage_handler.upload_file(self.key, tar_filename)
            os.remove(tar_filename)
            return self.key
        self.logger.debug(
            "Local path %s does not exist. Not uploading anything.",
            local_path)
        return None

    def get_compression(self):
        if self.storage_handler is not None:
            return self.storage_handler.get_compression()
        return None

    def _download_no_key_artifact(self):
        if self.is_mutable:
            self.logger.info("Downloading mutable artifact: %s",
                             self.name)
        if self.remote_path is None:
            msg: str =\
                "CANNOT download artifact without remote path: {0}"\
                    .format(self.name)
            util.report_fatal(msg, self.logger)

        key = self._generate_key()
        local_path = artifacts_tracker.get_blob_cache(key)
        local_path =\
            self._get_target_local_path(local_path, self.remote_path)
        if os.path.exists(local_path):
            msg: str = ('Immutable artifact exists at local_path {0},' +
                        ' skipping the download').format(local_path)
            self.logger.debug(msg)
            self.local_path = local_path
            return local_path

        if self.storage_handler.type == StorageType.storageDockerHub or \
           self.storage_handler.type == StorageType.storageSHub:
            msg: str = ('Qualified {0} points to a shub or dockerhub,' +
                        ' skipping the download').format(self.remote_path)
            self.logger.debug(msg)
            return self.remote_path

        self.storage_handler.download_remote_path(
            self.remote_path, local_path)

        self.logger.debug('Downloaded file %s from external source %s',
                          local_path, self.remote_path)
        self.local_path = local_path
        #self.key = key
        return self.local_path

    def _has_newer_artifact(self, local_path) -> bool:
        self.logger.debug(
            'Comparing date of the artifact %s in storage with local %s',
            self.key, local_path)
        storage_time = self.storage_handler.get_file_timestamp(self.key)
        local_time = os.path.getmtime(local_path)
        if storage_time is None:
            msg: str = \
                ("Unable to get storage timestamp for {0}, storage is either " + \
                 "corrupted or has not finished uploading").format(self.key)
            self.logger.info(msg)
            return False

        timestamp_shift = self.storage_handler.get_timestamp_shift()
        if local_time > storage_time - timestamp_shift:
            self.logger.debug(
                "Local path %s is younger than stored %s, skipping the download",
                local_path, self.key)
            return False

        return True

    def _download_and_untar_artifact(self, local_path):
        tar_filename: str = util.get_temp_filename()
        self.logger.debug("tar_filename = %s", tar_filename)

        # Now download our artifact from studio.storage and untar it:
        try:
            result: bool = \
                self.storage_handler.download_file(self.key, tar_filename)
            if not result:
                msg: str = \
                    "FAILED to download {0}.".format(self.key)
                self.logger.info(msg)
                return None
        except BaseException as exc:
            util.check_for_kb_interrupt()
            msg: str = \
                "FAILED to download {0}: {1}.".format(self.key, exc)
            self.logger.info(msg)
            return None

        if os.path.exists(tar_filename):
            untar_artifact(local_path, tar_filename, self.logger)
            os.remove(tar_filename)
            self.local_path = local_path
            return local_path
        self.logger.info('file %s download failed', tar_filename)
        return None

    def download(self, local_path=None, only_newer=True):
        if self.storage_handler is None:
            msg: str = "No storage handler is set for artifact {0}" \
                .format(self.key)
            util.report_fatal(msg, self.logger)

        if self.key is None:
            return self._download_no_key_artifact()

        if local_path is None:
            if self.local_path is not None and \
                    os.path.exists(self.local_path):
                local_path = self.local_path
            else:
                if self.is_mutable:
                    local_path = artifacts_tracker.get_artifact_cache(self.key)
                else:
                    local_path = artifacts_tracker.get_blob_cache(self.key)
                    if os.path.exists(local_path):
                        msg: str = ('Immutable artifact exists at local_path {0},' +
                                    ' skipping the download').format(local_path)
                        self.logger.debug(msg)
                        self.local_path = local_path
                        return local_path

        local_path = re.sub(r'\/\Z', '', local_path)
        self.logger.debug("Downloading dir %s to local path %s from studio.storage...",
                          self.key, local_path)

        if only_newer and os.path.exists(local_path):
            if not self._has_newer_artifact(local_path):
                return local_path

        # Now download our artifact from studio.storage and untar it:
        return self._download_and_untar_artifact(local_path)

    def _get_target_local_path(self, local_path: str, remote_path: str):
        result: str = local_path
        dir_name, file_name = \
            self.storage_handler.get_local_destination(remote_path)
        if dir_name is not None:
            result = os.path.join(result, dir_name)
        if file_name is not None:
            result = os.path.join(result, file_name)
        return result

    def delete(self):
        if self.key is not None:
            self.logger.debug('Deleting artifact: %s', self.key)
            self.storage_handler.delete_file(self.key, shallow=False)


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
        return url

    def _looks_like_local_file(self, url: str) -> bool:
        if url is None:
            return False

        local_prefix: str = "/"
        result = url.startswith(local_prefix)
        return result

    def stream(self):
        url = self.get_url()
        if url is None:
            return None

        # pylint: disable=consider-using-with

        # if our url is actually a local file reference
        # (can happen in local execution mode)
        # then we just open a local file:
        if self._looks_like_local_file(url):
            fileobj = open(url, 'rb')
        else:
            fileobj = urlopen(url)

        if fileobj:
            try:
                retval = tarfile.open(fileobj=fileobj, mode='r|*')
                return retval
            except BaseException as exc:
                util.check_for_kb_interrupt()
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
            tar_artifact(local_path, self.key,
                         self.get_compression(), self.logger)

        try:
            retval = util.sha256_checksum(tar_filename)
            os.remove(tar_filename)
            self.logger.debug('deleted local artifact file %s', tar_filename)
            return retval
        except BaseException as exc:
            util.check_for_kb_interrupt()
            self.logger.error(
                'error generating a hash for %s: %s',
                    tar_filename, repr(exc))
        return None

    def _is_s3_endpoint(self) -> bool:
        if self.remote_path is None:
            return False
        if self.remote_path.startswith('s3://'):
            return True
        if self.credentials is not None and\
            self.credentials.get_type() == credentials.AWS_TYPE:
            return True
        return False

    def _build_s3_config(self, art_dict):
        """
        For art_dict representing external S3-based artifact,
        build configuration suitable for constructing
        S3-based storage handler for this artifact.
        Returns: (configuration dictionary, artifact's S3 key)
        """
        url, bucket, key = util.parse_s3_path(self.remote_path)
        config = dict()
        config['endpoint'] = "http://{0}".format(url)
        config['bucket'] = bucket
        config[credentials.KEY_CREDENTIALS] =\
            self.credentials.to_dict() if self.credentials else dict()
        if 'region' in art_dict.keys():
            config['region'] = art_dict['region']

        return config, key

    def _build_http_config(self):
        """
        For external Http-based artifact,
        build configuration suitable for constructing
        Http-based storage handler for this artifact.
        """
        config = dict()
        config['endpoint'] = self.remote_path
        config[credentials.KEY_CREDENTIALS] =\
            self.credentials.to_dict() if self.credentials else dict()
        return config

    def _setup_storage_handler(self, art_dict):
        if self.key is not None:
            # Artifact is already stored in our shared blob-cache:
            self.storage_handler = storage_setup.get_storage_artifact_store()
            return

        if self.remote_path is not None:
            if self._is_s3_endpoint():
                s3_config_dict, _ = self._build_s3_config(art_dict)
                factory = StorageHandlerFactory.get_factory()
                self.storage_handler =\
                    factory.get_handler(StorageType.storageS3, s3_config_dict)
                return

            if self.remote_path.startswith('http://') or \
               self.remote_path.startswith('https://'):
                http_config_dict: Dict = self._build_http_config()
                factory = StorageHandlerFactory.get_factory()
                self.storage_handler =\
                    factory.get_handler(StorageType.storageHTTP, http_config_dict)
                return

        if self.local_path is not None:
            self.storage_handler =\
                storage_setup.get_storage_artifact_store()
            return

        raise NotImplementedError(
            "FAILED to setup storage handler for artifact: {0} {1}"
                .format(self.name, repr(art_dict)))

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

        if self.credentials is not None:
            result[credentials.KEY_CREDENTIALS] = self.credentials.to_dict()

        return result


    @property
    def in_blobstore(self) -> bool:
        if self.key is not None and self.key.startswith('blobstore/') and \
           self.storage_handler.get_file_timestamp(self.key) is not None:
            return True
        return False

    def _generate_key(self):
        return hashlib.sha256(self.remote_path.encode()).hexdigest()
