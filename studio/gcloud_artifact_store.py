import logging
import time
import calendar

from google.cloud import storage
from tartifact_store import TartifactStore
logging.basicConfig()


class GCloudArtifactStore(TartifactStore):
    def __init__(self, config, verbose=10, measure_timestamp_diff=True):
        self.logger = logging.getLogger('GCloudArtifactStore')
        self.logger.setLevel(verbose)
        self.client = storage.Client()

        try:
            self.bucket = self.client.get_bucket(config['bucket'])
        except BaseException:
            self.bucket = self.client.create_bucket(config['bucket'])

        super(GCloudArtifactStore, self).__init__(measure_timestamp_diff)

    def _upload_file(self, key, local_path):
        self.bucket.blob(key).upload_from_filename(local_path)

    def _download_file(self, key, local_path):
        self.bucket.get_blob(key).download_to_filename(local_path)

    def _delete_file(self, key):
        self.bucket.get_blob(key).delete()

    def _get_file_url(self, key):
        expiration = long(time.time() + 100000)
        return self.bucket.blob(key).generate_signed_url(expiration)

    def _get_file_timestamp(self, key):
        time_updated = self.bucket.get_blob(key).updated
        if time_updated:
            timestamp = calendar.timegm(time_updated.timetuple())
            return timestamp
        else:
            return None

    def get_qualified_location(self, key):
        return 'gs://' + self.bucket.name + '/' + key

    def get_bucket(self):
        return self.bucket.name
