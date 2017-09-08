import logging
import time
import calendar

from google.cloud import storage
from tartifact_store import TartifactStore

from auth import FirebaseAuth
import pyrebase
import json

logging.basicConfig()


class GCloudArtifactStore(TartifactStore):
    def __init__(self, config, verbose=10, measure_timestamp_diff=True):
        self.logger = logging.getLogger('GCloudArtifactStore')
        self.logger.setLevel(verbose)

        self.config = config

        try:
            self.bucket = self.getclient().get_bucket(config['bucket'])
        except BaseException as e:
            self.logger.exception(e)
            self.bucket = self.getclient().create_bucket(config['bucket'])

        super(GCloudArtifactStore, self).__init__(measure_timestamp_diff)

    def getclient(self):
        if 'credentials' in self.config.keys():
            return storage.Client \
                .from_service_account_json(config['serviceAccount'])
        else:
            return storage.Client()

    def _upload_file(self, key, local_path):
        self.bucket.blob(key).upload_from_filename(local_path)

    def _download_file(self, key, local_path):
        self.bucket.get_blob(key).download_to_filename(local_path)

    def _delete_file(self, key):
        blob = self.bucket.get_blob(key)
        if blob:
            blob.delete()

    def _get_file_url(self, key, method='GET'):

        expiration = long(time.time() + 100000)
        return self.bucket.blob(key).generate_signed_url(
            expiration,
            method=method)

    def _get_file_timestamp(self, key):
        blob = self.bucket.get_blob(key)
        if blob is None:
            return None
        time_updated = blob.updated
        if time_updated:
            timestamp = calendar.timegm(time_updated.timetuple())
            return timestamp
        else:
            return None

    def grant_write(self, key, user):
        blob = self.bucket.get_blob(key)
        if not blob:
            blob = self.bucket.blob(key)
            blob.upload_from_string("dummy")

        acl = blob.acl
        if user:
            acl.user(user).grant_owner()
        else:
            acl.all().grant_owner()

        acl.save()

    def get_qualified_location(self, key):
        return 'gs://' + self.bucket.name + '/' + key

    def get_bucket(self):
        return self.bucket.name
