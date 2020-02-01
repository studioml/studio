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
            self.bucket = config.get('bucket')
        self.store_root = os.path.join(self.store_root, self.bucket)
        self._ensure_path_dirs_exist(self.store_root)

        super(LocalArtifactStore, self).__init__(
            measure_timestamp_diff,
            compression=compression,
            verbose=verbose)

    def _ensure_path_dirs_exist(self, path):
        dirs = os.path.dirname(path)
        os.makedirs(dirs, mode = 0o777, exist_ok = True)

    def _upload_file(self, key, local_path):
        target_path = os.path.join(self.store_root, key)
        self._ensure_path_dirs_exist(target_path)
        shutil.copyfile(local_path, target_path)

    def _download_file(self, key, local_path, bucket=None):
        source_path = os.path.join(self.store_root, key)
        self._ensure_path_dirs_exist(local_path)
        shutil.copyfile(source_path, local_path)

    def _delete_file(self, key):
        os.remove(os.path.join(self.store_root, key))

    def _get_file_url(self, key, method='GET'):
        return str(os.path.join(self.store_root, key))

    def _get_file_post(self, key):
        return str(os.path.join(self.store_root, key))

    def _get_file_timestamp(self, key):
            return None

    def get_qualified_location(self, key):
        return 'file:/' + self.store_root + '/' + key

    def get_bucket(self):
        return self.bucket
