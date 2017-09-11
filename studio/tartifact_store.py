import os
import uuid

import logging
import time
import tempfile
import re
from threading import Thread
import subprocess

import fs_tracker
import util
import tarfile
import urllib

logging.basicConfig()


class TartifactStore(object):

    def __init__(self, measure_timestamp_diff=True):

        if measure_timestamp_diff:
            try:
                self.timestamp_shift = self._measure_timestamp_diff()
            except BaseException:
                self.timestamp_shift = 0
        else:
            self.timestamp_shift = 0

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

    def put_artifact(
            self,
            artifact,
            local_path=None,
            cache=True,
            background=False):
        if local_path is None:
            local_path = artifact['local']

        key = artifact.get('key')
        if os.path.exists(local_path):
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
                # self.logger.debug('.studioml_ignore found: %s,'
                #                   ' files listed inside will'
                #                   ' not be tarred or uploaded'
                #                   % ignore_filepath)

            if cache and key:
                cache_dir = fs_tracker.get_artifact_cache(key)
                if cache_dir != local_path:
                    debug_str = "Copying local path {} to cache {}" \
                        .format(local_path, cache_dir)
                    if ignore_arg != '':
                        debug_str += ", excluding files in {}" \
                            .format(ignore_filepath)
                    self.logger.debug(debug_str)

                    util.rsync_cp(local_path, cache_dir, ignore_arg,
                                  self.logger)

            debug_str = ("Tarring and uploading directrory. " +
                         "tar_filename = {}, " +
                         "local_path = {}, " +
                         "key = {}").format(
                tar_filename,
                local_path,
                key)
            if ignore_arg != '':
                debug_str += ", exclude = {}".format(ignore_filepath)
            self.logger.debug(debug_str)

            tarcmd = 'tar {} -czf {} -C {} {}'.format(
                ignore_arg,
                tar_filename,
                local_basepath,
                local_nameonly)
            self.logger.debug("Tar cmd = {}".format(tarcmd))

            tarp = subprocess.Popen(['/bin/bash', '-c', tarcmd],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    close_fds=True)

            tarout, _ = tarp.communicate()
            if tarp.returncode != 0:
                self.logger.info('tar had a non-zero return code!')
                self.logger.info('tar output: \n ' + tarout)

            if key is None:
                key = 'blobstore/' + util.sha256_checksum(tar_filename) \
                      + '.tgz'

            def finish_upload():
                self._upload_file(key, tar_filename)
                os.remove(tar_filename)

            t = Thread(target=finish_upload)
            t.start()

            if background:
                return (key, t)
            else:
                t.join()
                return key
        else:
            self.logger.debug(("Local path {} does not exist. " +
                               "Not uploading anything.").format(local_path))

    def get_artifact(
            self,
            artifact,
            local_path=None,
            only_newer=True,
            background=False):

        key = artifact['key']

        if local_path is None:
            if 'local' in artifact.keys() and \
                    os.path.exists(artifact['local']):
                local_path = artifact['local']
            else:
                if artifact['mutable']:
                    local_path = fs_tracker.get_artifact_cache(key)
                else:
                    local_path = fs_tracker.get_blob_cache(key)

        local_path = re.sub('\/\Z', '', local_path)
        local_basepath = os.path.dirname(local_path)

        self.logger.info("Downloading dir {} to local path {} from storage..."
                         .format(key, local_path))

        if only_newer and os.path.exists(local_path):
            self.logger.debug(
                'Comparing date of the artifact in storage with local')
            storage_time = self._get_file_timestamp(key)
            local_time = os.path.getmtime(local_path)
            if storage_time is None:
                self.logger.info(
                    "Unable to get storage timestamp, storage is either " +
                    "corrupted and has not finished uploading")
                return local_path

            if local_time > storage_time - self.timestamp_shift:
                self.logger.info(
                    "Local path is younger than stored, skipping the download")
                return local_path

        tar_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        self.logger.debug("tar_filename = {} ".format(tar_filename))

        def finish_download():
            self._download_file(key, tar_filename)
            if os.path.exists(tar_filename):
                # first, figure out if the tar file has a base path of .
                # or not
                self.logger.info("Untarring {}".format(tar_filename))
                listtar, _ = subprocess.Popen(['tar', '-tzf', tar_filename],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE,
                                              close_fds=True).communicate()
                listtar = listtar.strip().split('\n')
                self.logger.info('List of files in the tar: ' + str(listtar))
                if listtar[0].startswith('./'):
                    # Files are archived into tar from .; adjust path
                    # accordingly
                    basepath = local_path
                else:
                    basepath = local_basepath

                tarcmd = ('mkdir -p {} && ' +
                          'tar -xzf {} -C {} --keep-newer-files') \
                    .format(basepath, tar_filename, basepath)
                tarp = subprocess.Popen(
                    ['/bin/bash', '-c', tarcmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    close_fds=True)

                tarout, tarerr = tarp.communicate()
                if tarp.returncode != 0:
                    self.logger.info('tar had a non-zero return code!')
                    self.logger.info('tar cmd = ' + tarcmd)
                    self.logger.info('tar output: \n ' + tarout)

                if len(listtar) == 1:
                    actual_path = os.path.join(basepath, listtar[0])
                    self.logger.info(
                        'Renaming {} into {}'.format(
                            actual_path, local_path))
                    os.rename(actual_path, local_path)
                os.remove(tar_filename)
            else:
                self.logger.warn(
                    'file {} download failed'.format(tar_filename))

        t = Thread(target=finish_download)
        t.start()
        if background:
            return (local_path, t)
        else:
            t.join()
            return local_path

    def get_artifact_url(self, artifact, method='GET', get_timestamp=False):
        if 'key' in artifact.keys():
            url = self._get_file_url(artifact['key'], method=method)
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

        fileobj = urllib.urlopen(url)
        if fileobj:
            try:
                retval = tarfile.open(fileobj=fileobj, mode='r|gz')
                return retval
            except BaseException as e:
                self.logger.info('Streaming artifact error:\n' + e.message)
        return None
