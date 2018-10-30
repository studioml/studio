import time
import calendar

from .tartifact_store import TartifactStore
from . import logs


STORAGE_CLIENT_EXPIRATION = 3600


class GCloudArtifactStore(TartifactStore):
    def __init__(self, config,
                 measure_timestamp_diff=False,
                 compression=None,
                 verbose=10):

        self.logger = logs.getLogger('GCloudArtifactStore')
        self.logger.setLevel(verbose)

        self.config = config
        self._client = None
        self._client_timestamp = None

        compression = compression if compression else config.get('compression')

        super(GCloudArtifactStore, self).__init__(
            measure_timestamp_diff,
            compression=compression)

    def _get_bucket_obj(self):

        while True:
            try:
                bucket = self.get_client().get_bucket(self.config['bucket'])
                break
            except BaseException as e:
                self.logger.exception(e)
                try:
                    bucket = self.get_client().create_bucket(
                        self.config['bucket'])
                    break
                except BaseException as e:
                    self.logger.exception(e)
            time.sleep(5)

        return bucket

    def get_client(self):
        if self._client is None or \
           self._client_timestamp is None or \
           time.time() - self._client_timestamp > STORAGE_CLIENT_EXPIRATION:

            from google.cloud import storage
            if 'credentials' in self.config.keys():
                self._client = storage.Client \
                    .from_service_account_json(self.config['serviceAccount'])
            else:
                self._client = storage.Client()
            self._client_timestamp = time.time()

        return self._client

    def _upload_file(self, key, local_path):
        self._get_bucket_obj().blob(key).upload_from_filename(local_path)

    def _download_file(self, key, local_path, bucket=None):
        self._get_bucket_obj().get_blob(key).download_to_filename(local_path)

    def _delete_file(self, key):
        blob = self._get_bucket_obj().get_blob(key)
        if blob:
            blob.delete()

    def _get_file_url(self, key, method='GET'):
        expiration = int(time.time() + 100000)
        return self._get_bucket_obj().blob(key).generate_signed_url(
            expiration,
            method=method)

    def _get_file_timestamp(self, key):
        blob = self._get_bucket_obj().get_blob(key)
        if blob is None:
            return None
        time_updated = blob.updated
        if time_updated:
            timestamp = calendar.timegm(time_updated.timetuple())
            return timestamp
        else:
            return None

    def grant_write(self, key, user):
        blob = self._get_bucket_obj().get_blob(key)
        if not blob:
            blob = self._get_bucket_obj().blob(key)
            blob.upload_from_string("dummy")

        acl = blob.acl
        if user:
            acl.user(user).grant_owner()
        else:
            acl.all().grant_owner()

        acl.save()

    def get_qualified_location(self, key):
        return 'gs://' + self.get_bucket() + '/' + key

    def get_bucket(self):
        return self._get_bucket_obj().name
