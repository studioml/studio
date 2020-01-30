import os
import json

from .keyvalue_provider import KeyValueProvider
from .local_artifact_store import LocalArtifactStore

class LocalDbProvider(KeyValueProvider):

    single_instance = None

    @classmethod
    def get_instance(cls, config, blocking_auth=True, verbose=10, store=None):
        if LocalDbProvider.single_instance is None:
            LocalDbProvider.single_instance = \
                LocalDbProvider(config, blocking_auth, verbose, store)
        return LocalDbProvider.single_instance

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        print(">>>>>> LocalDbProvider constructor")

        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.endpoint = config.get('endpoint', '~')
        self.store_root = os.path.realpath(os.path.expanduser(self.endpoint))
        if not os.path.exists(self.store_root) \
            or not os.path.isdir(self.store_root):
            raise ValueError()

        self.bucket = config.get('bucket')
        self.store_root = os.path.join(self.store_root, self.bucket)
        self._ensure_path_dirs_exist(self.store_root)

        self.meta_store = LocalArtifactStore(config, self.bucket, verbose)

        super(LocalDbProvider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

        self.db_dict = {}

    def _ensure_path_dirs_exist(self, path):
        dirs = os.path.dirname(path)
        os.makedirs(dirs, mode = 0o777, exist_ok = True)

    def _get(self, key, shallow=False):
        file_name = os.path.join(self.store_root, key)
        if not os.path.exists(file_name):
            return None
        with open(file_name) as infile:
            result = json.load(infile)
        return result

    def _delete(self, key):
        file_name = os.path.join(self.store_root, key)
        if os.path.exists(file_name):
            os.remove(file_name)

    def _set(self, key, value):
        file_name = os.path.join(self.store_root, key)
        self._ensure_path_dirs_exist(file_name)
        with open(file_name, 'w') as outfile:
            json.dump(value, outfile)
        
