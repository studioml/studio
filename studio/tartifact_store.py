import os
import uuid

import time
import tempfile
import re
import subprocess

import tarfile
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

import hashlib

from . import fs_tracker, logs
from . import util
from .util import download_file, download_file_from_qualified, retry
from .util import compression_to_extension, compression_to_taropt, timeit
from .util import sixdecode

from .base_artifact_store import BaseArtifactStore


class TartifactStore(BaseArtifactStore):

    def __init__(self, measure_timestamp_diff=False, compression=None,
                 verbose=logs.DEBUG):

        super(TartifactStore, self).__init__()

        if measure_timestamp_diff:
            try:
                self.timestamp_shift = self._measure_timestamp_diff()
            except BaseException:
                self.timestamp_shift = 0
        else:
            self.timestamp_shift = 0

        self.compression = compression

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

    def _report_fatal(self, msg: str):
        self.logger.error(msg)
        raise ValueError(msg)

    def _measure_timestamp_diff(self):

        max_diff = 60

        tmpfile = os.path.join(
            tempfile.gettempdir(), str(
                uuid.uuid4()) + '.txt')
        with open(tmpfile, 'w') as f:
            f.write('timestamp_diff_test')
        key = 'tests/' + str(uuid.uuid4())
        self._upload_file(key, tmpfile)
        remote_timestamp = self._get_file_timestamp(key)

        if remote_timestamp is not None:

            now_remote_diff = time.time() - remote_timestamp
            self._delete_file(key)
            os.remove(tmpfile)

            assert -max_diff < now_remote_diff and \
                now_remote_diff < max_diff, \
                "Timestamp difference is more than 60 seconds. " + \
                "You'll need to adjust local clock for caching " + \
                "to work correctly"

            return -now_remote_diff if now_remote_diff < 0 else 0

    def get_artifact_hash(
            self,
            artifact,
            local_path=None):

        if local_path is None:
            local_path = artifact['local']

        if local_path is None or not os.path.exists(local_path):
            if artifact.get('qualified'):
                return hashlib.sha256(artifact.get('qualified')).hexdigest()
            elif artifact.get('url'):
                return hashlib.sha256(artifact.get('url')).hexdigest()

        key = artifact.get('key')
        tar_filename = self._tartifact(local_path, key)

        try:
            retval = util.sha256_checksum(tar_filename)
            os.remove(tar_filename)
            self.logger.debug(
                'deleted local artifact file {0}'.format(tar_filename))
            return retval
        except BaseException as e:
            self.logger.error(
                'error generating a hash for {0}: {1}'
                    .format(tar_filename, repr(e)))

        return None

    def put_artifact(
            self,
            artifact,
            local_path=None):
        if local_path is None:
            local_path = artifact.get('local')

        key = artifact.get('key')

        if key and key.startswith('blobstore/') and \
           self._get_file_timestamp(key) is not None:
            self.logger.debug(('Artifact with key {0} exists in blobstore, ' +
                              'skipping the upload').format(key))

            return key

        if os.path.exists(local_path):
            tar_filename = self._tartifact(local_path, key)
            if key is None:
                key = 'blobstore/' + util.sha256_checksum(tar_filename) \
                      + '.tar' + compression_to_extension(self.compression)
                if self._get_file_timestamp(key) is not None:
                    self.logger.debug(
                        ('Artifact with key {0} exists in blobstore, ' +
                         'skipping the upload').format(key))

                    os.remove(tar_filename)
                    return key

            self._upload_file(key, tar_filename)
            os.remove(tar_filename)
            return key
        else:
            self.logger.debug(("Local path {0} does not exist. " +
                               "Not uploading anything.").format(local_path))
            return None

    def get_artifact(
            self,
            artifact,
            local_path=None,
            only_newer=True):

        key = artifact.get('key')

        if key is None:
            assert not artifact['mutable']
            assert artifact.get('url') is not None or \
                artifact.get('qualified') is not None

            remote_path = artifact.get('url')
            if remote_path is None:
                remote_path = artifact.get('qualified')

            key = hashlib.sha256(remote_path.encode()).hexdigest()
            local_path = fs_tracker.get_blob_cache(key)
            if os.path.exists(local_path):
                self.logger.debug((
                    'Immutable artifact exists at local_path {0},' +
                    ' skipping the download').format(local_path))
                return local_path

            if artifact.get('url') is not None:
                download_file(remote_path, local_path, self.logger)
            else:
                if remote_path.startswith('dockerhub://') or \
                   remote_path.startswith('shub://'):
                    self.logger.debug((
                        'Qualified {0} points to a shub or dockerhub,' +
                        ' skipping the download'.format(remote_path)))
                    return remote_path

                download_file_from_qualified(
                    remote_path, local_path, self.logger)

            self.logger.debug('Downloaded file {0} from external source {1}'
                              .format(local_path, remote_path))
            return local_path

        if local_path is None:
            if 'local' in artifact.keys() and \
                    os.path.exists(artifact['local']):
                local_path = artifact['local']
            else:
                if artifact['mutable']:
                    local_path = fs_tracker.get_artifact_cache(key)
                else:
                    local_path = fs_tracker.get_blob_cache(key)
                    if os.path.exists(local_path):
                        self.logger.debug((
                            'Immutable artifact exists at local_path {0},' +
                            ' skipping the download').format(local_path))
                        return local_path

        local_path = re.sub('\/\Z', '', local_path)
        local_basepath = os.path.dirname(local_path)

        self.logger.debug("Downloading dir {0} to local path {1} from storage..."
                         .format(key, local_path))

        if only_newer and os.path.exists(local_path):
            self.logger.debug(
                'Comparing date of the artifact {0} in storage with local {1}'
                    .format(key, local_path))
            storage_time = self._get_file_timestamp(key)
            local_time = os.path.getmtime(local_path)
            if storage_time is None:
                msg: str =\
                    "Unable to get storage timestamp for {0}, storage is either " +\
                    "corrupted or has not finished uploading".format(key)
                self._report_fatal(msg)
                return local_path

            if local_time > storage_time - self.timestamp_shift:
                self.logger.debug(
                    "Local path {0} is younger than stored {1}, skipping the download"
                        .format(local_path, key))
                return local_path

        tar_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        self.logger.debug("tar_filename = {0} ".format(tar_filename))

        def finish_download():
            try:
                result = self._download_file(key, tar_filename)
                if not result:
                    return local_path
            except BaseException as exc:
                msg: str =\
                    "FAILED to download {0}: {1}. Aborting.".format(key, exc)
                self._report_fatal(msg)

            if os.path.exists(tar_filename):
                # first, figure out if the tar file has a base path of .
                # or not
                self.logger.debug("Untarring {0}".format(tar_filename))
                listtar, _ = subprocess.Popen(['tar', '-tf', tar_filename],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE,
                                              close_fds=True
                                              ).communicate()
                listtar = listtar.strip().split(b'\n')
                listtar = [s.decode('utf-8') for s in listtar]

                isTarFromDotDir = False
                self.logger.debug('List of files in the tar: ' + str(listtar))
                if listtar[0].startswith('./'):
                    # Files are archived into tar from .; adjust path
                    # accordingly
                    isTarFromDotDir = True
                    basepath = local_path
                else:
                    basepath = local_basepath

                tarcmd = ('mkdir -p {} && ' +
                          'tar -xf {} -C {} --keep-newer-files') \
                    .format(basepath, tar_filename, basepath)

                self.logger.debug('Tar cmd = {0}'.format(tarcmd))

                tarp = subprocess.Popen(
                    ['/bin/bash', '-c', tarcmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    close_fds=True)

                tarout, tarerr = tarp.communicate()
                if tarp.returncode != 0:
                    msg: str = 'tar {0} had a non-zero return code! {1}'\
                        .format(tar_filename, tarp.returncode)
                    msg += 'tar cmd = {0}'.format(tarcmd)
                    msg = msg + 'tar stdout output: \n ' + str(tarout)
                    msg = msg + 'tar stderr output: \n ' + str(tarerr)
                    self._report_fatal(msg)

                if len(listtar) == 1 and not isTarFromDotDir:
                    # Here we protect ourselves from the corner case,
                    # when we try to move A/. folder to A.
                    # os.rename() will fail to do that.
                    actual_path = os.path.join(basepath, listtar[0])
                    self.logger.debug(
                        'Renaming {0} into {1}'.format(
                            actual_path, local_path))
                    retry(lambda: os.rename(actual_path, local_path),
                          no_retries=5,
                          sleep_time=1,
                          exception_class=OSError,
                          logger=self.logger)

                os.remove(tar_filename)
            else:
                self._report_fatal('file {0} download failed'
                                   .format(tar_filename))

        finish_download()
        return local_path

    def get_artifact_url(self, artifact, method='GET', get_timestamp=False):
        if 'key' in artifact.keys():
            url = self._get_file_url(artifact['key'], method=method)
        elif 'url' in artifact.keys():
            url = artifact['url']
        else:
            url = None

        if get_timestamp:
            timestamp = self._get_file_timestamp(artifact['key'])
            return (url, timestamp)
        else:
            return url

        return None

    def get_artifact_post(self, artifact):
        if 'key' in artifact.keys():
            return self._get_file_post(artifact['key'])
        return None

    def delete_artifact(self, artifact):
        if 'key' in artifact.keys():
            self._delete_file(artifact['key'])

    def stream_artifact(self, artifact):
        url = self.get_artifact_url(artifact)
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
                self._report_fatal(msg)
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def _tartifact(self, local_path, key, cache=True):

        tar_filename = os.path.join(tempfile.gettempdir(),
                                    str(uuid.uuid4()))

        if os.path.isdir(local_path):
            local_basepath = local_path
            local_nameonly = '.'

        else:
            local_nameonly = os.path.basename(local_path)
            local_basepath = os.path.dirname(local_path)

        ignore_arg = ''
        ignore_filepath = os.path.join(local_basepath, ".studioml_ignore")
        if os.path.exists(ignore_filepath) and \
                not os.path.isdir(ignore_filepath):
            ignore_arg = "--exclude-from=%s" % ignore_filepath
            self.logger.debug('.studioml_ignore found: {0},'
                              ' files listed inside will'
                              ' not be tarred or uploaded'
                              .format(ignore_filepath))

        if cache and key:
            cache_dir = fs_tracker.get_artifact_cache(key)
            if cache_dir != local_path:
                debug_str = "Copying local path {0} to cache {1}" \
                    .format(local_path, cache_dir)
                if ignore_arg != '':
                    debug_str += ", excluding files in {0}" \
                        .format(ignore_filepath)
                self.logger.debug(debug_str)

                util.rsync_cp(local_path, cache_dir, ignore_arg,
                              self.logger)

        debug_str = ("Tarring artifact. " +
                     "tar_filename = {0}, " +
                     "local_path = {1}, " +
                     "key = {2}").format(tar_filename, local_path, key)

        if ignore_arg != '':
            debug_str += ", exclude = {0}".format(ignore_filepath)
        self.logger.debug(debug_str)

        tarcmd = 'tar {0} {1} -cf {2} -C {3} {4}'.format(
            ignore_arg,
            compression_to_taropt(self.compression),
            tar_filename,
            local_basepath,
            local_nameonly)
        self.logger.debug("Tar cmd = {0}".format(tarcmd))

        tic = time.time()
        tarp = subprocess.Popen(['/bin/bash', '-c', tarcmd],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                close_fds=True)

        tarout, tarerr = tarp.communicate()
        toc = time.time()

        if tarp.returncode != 0:
            msg: str = 'tar {0} had a non-zero return code! {1}' \
                .format(tar_filename, tarp.returncode)
            msg += 'tar cmd = {0}'.format(tarcmd)
            msg = msg + 'tar stdout output: \n ' + sixdecode(tarout)
            msg = msg + 'tar stderr output: \n ' + str(tarerr)
            self._report_fatal(msg)

        self.logger.debug('tar finished in {0}s'.format(toc - tic))
        return tar_filename


def get_immutable_artifact_key(arthash, compression=None):
    retval = "blobstore/" + arthash + ".tar" + \
             compression_to_extension(compression)
    return retval
