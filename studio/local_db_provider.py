import os
import json

from .keyvalue_provider import KeyValueProvider

class LocalDbProvider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.endpoint = config.get('endpoint', '~')
        self.db_root = os.path.realpath(os.path.expanduser(self.endpoint))
        if not os.path.exists(self.db_root) \
            or not os.path.isdir(self.db_root):
            raise ValueError("Local DB root {0} doesn't exist or not a directory!".format(self.db_root))

        self.bucket = config.get('bucket')
        self.db_root = os.path.join(self.db_root, self.bucket)
        self._ensure_path_dirs_exist(self.db_root)

        super(LocalDbProvider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

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

    def _delete(self, key):
        file_name = os.path.join(self.db_root, key)
        if os.path.exists(file_name):
            os.remove(file_name)

    def _set(self, key, value):
        file_name = os.path.join(self.db_root, key)
        self._ensure_path_dirs_exist(file_name)
        with open(file_name, 'w') as outfile:
            json.dump(value, outfile)
        
