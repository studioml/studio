import time
import calendar
import certifi
import json

from . import pyrebase
from . import logs
from .auth import get_auth
from .tartifact_store import TartifactStore


class FirebaseArtifactStore(TartifactStore):

    def __init__(self, db_config,
                 measure_timestamp_diff=False,
                 blocking_auth=True,
                 compression=None,
                 verbose=10):

        guest = db_config.get('guest')

        self.app = pyrebase.initialize_app(db_config)

        if compression is None:
            compression = db_config.get('compression')

        self.auth = None
        if not guest and 'serviceAccount' not in db_config.keys():
            self.auth = get_auth(self.app,
                                 db_config.get("use_email_auth"),
                                 db_config.get("email"),
                                 db_config.get("password"),
                                 blocking_auth)

        self.logger = logs.getLogger('FirebaseArtifactStore')
        self.logger.setLevel(verbose)
        super(FirebaseArtifactStore, self).__init__(
            measure_timestamp_diff,
            compression=compression)

    def _upload_file(self, key, local_file_path):
        try:
            storageobj = self.app.storage().child(key)
            if self.auth:
                storageobj.put(local_file_path,
                               self.auth.get_token(),
                               self.auth.get_user_id())
            else:
                storageobj.put(local_file_path)
        except Exception as err:
            self.logger.debug(("Uploading file {} with key {} into storage " +
                               "raised an exception: {}")
                              .format(local_file_path, key, err))

    def _download_file(self, key, local_file_path, bucket=None):
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

                response = self.app.requests.get(
                    url,
                    stream=True,
                    headers=headers,
                    verify=certifi.old_where())
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
            self.logger.warn(
                ("Downloading file {} to local path {} from storage " +
                 "raised an exception: {}") .format(
                    key,
                    local_file_path,
                    err))

    def _delete_file(self, key):
        self.logger.debug("Deleting file at key {}".format(key))
        try:
            if self.auth:

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
            else:
                headers = {}

            escaped_key = key.replace('/', '%2f')
            url = "{}/o/{}?alt=media".format(
                self.app.storage().storage_bucket,
                escaped_key)

            response = self.app.requests.delete(
                url, headers=headers, verify=certifi.old_where())
            if response.status_code != 204:
                raise ValueError("Response error with code {}, text {}"
                                 .format(response.status_code, response.text))

            self.logger.debug("Done")
        except Exception as err:
            self.logger.warning(
                ("Deleting file {} from storage " +
                 "raised an exception: {}") .format(key, err))

    def _get_file_url(self, key, method='GET'):
        assert method == 'GET'
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
            if self.auth and self.auth.get_token():
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

            response = self.app.requests.get(
                url, headers=headers, verify=certifi.old_where())
            if response.status_code != 200:
                self.logger.debug("Response error with code {}"
                                  .format(response.status_code))
                return (None, None)

            return (json.loads(response.content.decode()), url)

        except Exception as err:
            self.logger.warn(
                ("Getting metainfo of file {} " +
                 "raised an exception: {}") .format(key, err))
            self.logger.exception(err)
            return (None, None)

    def get_qualified_location(self, key):
        return 'gs://' + self.app.storage_bucket + '/' + key

    def get_bucket(self):
        return self.app.storage_bucket

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.app.requests.close()
