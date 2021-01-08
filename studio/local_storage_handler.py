import os
import shutil

from .model_setup import get_model_verbose_level
from .storage_type import StorageType
from .storage_handler import StorageHandler
from . import logs
from . import util

class LocalStorageHandler(StorageHandler):
    def __init__(self, config,
                 measure_timestamp_diff=False,
                 compression=None):

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())

        if compression is None:
            compression = config.get('compression')

        self.endpoint = config.get('endpoint', '~')
        self.endpoint = os.path.realpath(os.path.expanduser(self.endpoint))
        if not os.path.exists(self.endpoint) \
            or not os.path.isdir(self.endpoint):
            msg: str = "Store root {0} doesn't exist or not a directory. Aborting."\
                .format(self.endpoint)
            self._report_fatal(msg)

        self.bucket = config.get('bucket', 'storage')
        self.store_root = os.path.join(self.endpoint, self.bucket)
        self._ensure_path_dirs_exist(self.store_root)

        super().__init__(StorageType.storageLocal,
            self.logger,
            measure_timestamp_diff,
            compression=compression)

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

    def upload_file(self, key, local_path):
        target_path = os.path.join(self.store_root, key)
        if not os.path.exists(local_path):
            self.logger.debug(
                "Local path {0} does not exist. SKIPPING upload to {1}"
                    .format(local_path, target_path))
            return False
        self._ensure_path_dirs_exist(target_path)
        self._copy_file(local_path, target_path)
        return True

    def download_file(self, key, local_path):
        source_path = os.path.join(self.store_root, key)
        if not os.path.exists(source_path):
            self.logger.debug(
                "Source path {0} does not exist. SKIPPING download to {1}"
                    .format(source_path, local_path))
            return False
        self._ensure_path_dirs_exist(local_path)
        self._copy_file(source_path, local_path)
        return True

    def delete_file(self, key, shallow=True):
        key_path: str = self._get_file_path_from_key(key)
        if os.path.exists(key_path):
            self.logger.debug("Deleting local file {0}.".format(key_path))
            util.delete_local_path(key_path, self.store_root, False)

    def _get_file_path_from_key(self, key: str):
        return str(os.path.join(self.store_root, key))

    def get_file_url(self, key, method='GET'):
        return self._get_file_path_from_key(key)

    def get_file_timestamp(self, key):
        key_path: str = self._get_file_path_from_key(key)
        if os.path.exists(key_path):
            return os.path.getmtime(key_path)
        else:
            return None

    def get_qualified_location(self, key):
        return 'file:/' + self.store_root + '/' + key

    def get_endpoint(self):
        return self.endpoint

    def _report_fatal(self, msg: str):
        util.report_fatal(msg, self.logger)
