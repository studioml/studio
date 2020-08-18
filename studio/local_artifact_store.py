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
            msg: str = "Store root {0} doesn't exist or not a directory. Aborting."\
                .format(self.store_root)
            self._report_fatal(msg)

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

    def _copy_file(self, from_path, to_path):
        try:
            shutil.copyfile(from_path, to_path)
        except Exception as exc:
            msg: str = "FAILED to copy '{0}' to '{1}': {2}. Aborting."\
                .format(from_path, to_path,exc)
            self._report_fatal(msg)

    def _upload_file(self, key, local_path):
        target_path = os.path.join(self.store_root, key)
        if not os.path.exists(local_path):
            self.logger.info(
                "Local path {0} does not exist. SKIPPING upload to {1}"
                    .format(local_path, target_path))
            return False
        self._ensure_path_dirs_exist(target_path)
        self._copy_file(local_path, target_path)
        return True

    def _download_file(self, key, local_path, bucket=None):
        source_path = os.path.join(self.store_root, key)
        if not os.path.exists(source_path):
            self.logger.info(
                "Source path {0} does not exist. SKIPPING download to {1}"
                    .format(source_path, local_path))
            return False
        self._ensure_path_dirs_exist(local_path)
        self._copy_file(source_path, local_path)
        return True

    def _delete_file(self, key):
        os.remove(os.path.join(self.store_root, key))

    def _get_file_path_from_key(self, key: str):
        return str(os.path.join(self.store_root, key))

    def _get_file_url(self, key, method='GET'):
        return self._get_file_path_from_key(key)

    def _get_file_post(self, key):
        return self._get_file_path_from_key(key)

    def _get_file_timestamp(self, key):
        key_path: str = self._get_file_path_from_key(key)
        if os.path.exists(key_path):
            return os.path.getmtime(key_path)
        else:
            return None

    def get_qualified_location(self, key):
        return 'file:/' + self.store_root + '/' + key

    def get_bucket(self):
        return self.bucket
