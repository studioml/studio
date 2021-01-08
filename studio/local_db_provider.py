import os
import json

from .keyvalue_provider import KeyValueProvider
from .local_storage_handler import LocalStorageHandler
from . import util

class LocalDbProvider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True):
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = LocalStorageHandler(config)

        self.endpoint = self.meta_store.get_endpoint()
        self.db_root = os.path.join(self.endpoint, self.bucket)
        self._ensure_path_dirs_exist(self.db_root)

        super().__init__(config, self.meta_store, blocking_auth)

    def _ensure_path_dirs_exist(self, path):
        dirs = os.path.dirname(path)
        os.makedirs(dirs, mode = 0o777, exist_ok = True)

    def _get(self, key, shallow=False):
        file_name = os.path.join(self.db_root, key)
        if not os.path.exists(file_name):
            return None
        with open(file_name) as infile:
            result = json.load(infile)
        return result

    def _delete(self, key, shallow=True):
        file_name = os.path.join(self.db_root, key)
        if os.path.exists(file_name):
            self.logger.debug("Deleting local database file {0}.".format(file_name))
            util.delete_local_path(file_name, self.db_root, shallow)

    def _set(self, key, value):
        file_name = os.path.join(self.db_root, key)
        self._ensure_path_dirs_exist(file_name)
        with open(file_name, 'w') as outfile:
            json.dump(value, outfile)

