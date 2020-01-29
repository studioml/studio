import calendar
import os
import shutil

from .tartifact_store import TartifactStore

class LocalArtifactStore(TartifactStore):
    def __init__(self, config,
                 bucket_name=None,
                 verbose=10,
                 measure_timestamp_diff=False,
                 compression=None):

        if compression is None:
            compression = config.get('compression')

        self.endpoint = config.get('endpoint', '~')
        self.store_root = os.path.realpath(os.path.expanduser(self.endpoint))
        if not os.path.exists(self.store_root) \
            or not os.path.isdir(self.store_root):
            raise ValueError()

        self.bucket = bucket_name
        if self.bucket is None:
            self.bucket = config('bucket')
        self.store_root = os.path.join(self.store_root, self.bucket)

        super(LocalArtifactStore, self).__init__(
            measure_timestamp_diff,
            compression=compression,
            verbose=verbose)


    def _upload_file(self, key, local_path):
        shutil.copyfile(local_path, os.path.join(self.store_root, key))

    def _download_file(self, key, local_path, bucket=None):
        shutil.copyfile(os.path.join(self.store_root, key), local_path)

    def _delete_file(self, key):
        os.remove(os.path.join(self.store_root, key))

    def _get_file_url(self, key, method='GET'):
        return str(os.path.join(self.store_root, key))

    def _get_file_post(self, key):
        return str(os.path.join(self.store_root, key))

    def _get_file_timestamp(self, key):
            return None

    def get_qualified_location(self, key):
        return 'file://' + self.endpoint + '/' + self.bucket + '/' + key

    def get_bucket(self):
        return self.bucket
