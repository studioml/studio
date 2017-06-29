import os
import uuid

import logging
import time
import calendar
import tempfile
import re
from threading import Thread
import subprocess
import requests
import json
import shutil

import fs_tracker
import util

logging.basicConfig()


class FirebaseArtifactStore(object):

    def __init__(self, pyrebase_app, auth):
        self.app = pyrebase_app
        self.auth = auth
        self.logger = logging.getLogger('FirebaseArtifactStore')
        self.logger.setLevel(10)

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

            local_path = re.sub('/\Z', '', local_path)
            local_nameonly = re.sub('.*/', '', local_path)
            local_basepath = re.sub('/[^/]*\Z', '', local_path)

            if cache and key:
                cache_dir = fs_tracker.get_artifact_cache(key)
                if cache_dir != local_path:
                    self.logger.debug(
                        "Copying local path {} to cache {}"
                        .format(local_path, cache_dir))

                    if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
                        shutil.rmtree(cache_dir)

                    subprocess.call(['cp', '-pR', local_path, cache_dir])

            self.logger.debug(
                ("Tarring and uploading directrory. " +
                 "tar_filename = {}, " +
                 "local_path = {}, " +
                 "key = {}").format(
                    tar_filename,
                    local_path,
                    key))

            tarcmd = 'tar -czf {} -C {} {}'.format(
                tar_filename,
                local_basepath,
                local_nameonly)

            self.logger.debug("Tar cmd = {}".format(tarcmd))

            subprocess.call(['/bin/bash', '-c', tarcmd])

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

        self.logger.debug("Downloading dir {} to local path {} from storage..."
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

            if local_time > storage_time:
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
                self.logger.debug("Untarring {}".format(tar_filename))
                listtar, _ = subprocess.Popen(['tar', '-tzf', tar_filename],
                                              stdout=subprocess.PIPE
                                              ).communicate()
                listtar = listtar.strip().split('\n')
                self.logger.debug('List of files in the tar: ' + str(listtar))
                if listtar[0].startswith('./'):
                    # Files are archived into tar from .; adjust path
                    # accordingly
                    basepath = local_path
                else:
                    basepath = local_basepath

                subprocess.call([
                    '/bin/bash',
                    '-c',
                    ('mkdir -p {} &&' +
                     'tar -xzf {} -C {} --keep-newer-files')
                    .format(basepath, tar_filename, basepath)])

                if len(listtar) == 1:
                    actual_path = os.path.join(basepath, listtar[0])
                    self.logger.info(
                        'Renaming {} into {}'.format(
                            actual_path, local_path))
                    os.rename(actual_path, local_path)
                os.remove(tar_filename)
            else:
                self.logger.error(
                    'file {} download failed'.format(tar_filename))

        t = Thread(target=finish_download)
        t.start()
        if background:
            return (local_path, t)
        else:
            t.join()
            return local_path

    def get_artifact_url(self, artifact):
        if 'key' in artifact.keys():
            return self._get_file_url(artifact['key'])
        return None

    def delete_artifact(self, artifact):
        if 'key' in artifact.keys():
            self._delete_file(artifact['key'])

    def _upload_file(self, key, local_file_path):
        try:
            storageobj = self.app.storage().child(key)
            if self.auth:
                storageobj.put(local_file_path, self.auth.get_token())
            else:
                storageobj.put(local_file_path)
        except Exception as err:
            self.logger.error(("Uploading file {} with key {} into storage " +
                               "raised an exception: {}")
                              .format(local_file_path, key, err))

    def _download_file(self, key, local_file_path):
        self.logger.debug("Downloading file at key {} to local path {}..."
                          .format(key, local_file_path))
        try:
            storageobj = self.app.storage().child(key)

            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
                escaped_key = key.replace('/', '%2f')
                url = "{}/o/{}?alt=media".format(
                    self.app.storage().storage_bucket,
                    escaped_key)

                response = requests.get(url, stream=True, headers=headers)
                if response.status_code == 200:
                    with open(local_file_path, 'wb') as f:
                        for chunk in response:
                            f.write(chunk)
                else:
                    raise ValueError("Response error with code {}"
                                     .format(response.status_code))
            else:
                storageobj.download(local_file_path)
            self.logger.debug("Done")
        except Exception as err:
            self.logger.error(
                ("Downloading file {} to local path {} from storage " +
                 "raised an exception: {}") .format(
                    key,
                    local_file_path,
                    err))

    def _delete_file(self, key):
        self.logger.debug("Downloading file at key {}".format(key))
        try:
            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
            else:
                headers = {}

            escaped_key = key.replace('/', '%2f')
            url = "{}/o/{}?alt=media".format(
                self.app.storage().storage_bucket,
                escaped_key)

            response = requests.delete(url, headers=headers)
            if response.status_code != 204:
                raise ValueError("Response error with code {}"
                                 .format(response.status_code))

            self.logger.debug("Done")
        except Exception as err:
            self.logger.error(
                ("Deleting file {} from storage " +
                 "raised an exception: {}") .format(key, err))

    def _get_file_url(self, key):
        self.logger.debug("Getting a download url for a file at key {}"
                          .format(key))

        response_dict, url = self._get_file_meta(key)
        if response_dict is None:
            self.logger.debug("Getting file metainfo failed")
            return None

        self.logger.debug("Done")
        return url + '?alt=media&token=' \
            + response_dict['downloadTokens']

    def _get_file_timestamp(self, key):
        response, _ = self._get_file_meta(key)
        if response is not None and 'updated' in response.keys():
            timestamp = calendar.timegm(
                time.strptime(
                    response['updated'],
                    "%Y-%m-%dT%H:%M:%S.%fZ"))
            return timestamp
        else:
            return None

    def _get_file_meta(self, key):
        self.logger.debug("Getting metainformation for a file at key {}"
                          .format(key))
        try:
            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
            else:
                headers = {}

            escaped_key = key.replace('/', '%2f')
            url = "{}/o/{}".format(
                self.app.storage().storage_bucket,
                escaped_key)

            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise ValueError("Response error with code {}"
                                 .format(response.status_code))

            return (json.loads(response.content), url)

        except Exception as err:
            self.logger.error(
                ("Getting metainfo of file {} " +
                 "raised an exception: {}") .format(key, err))
            return (None, None)
