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
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = LocalArtifactStore(config, self.bucket, verbose)

        super(LocalDbProvider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

        self.db_dict = {}

    def _get(self, key, shallow=False):
        return self.db_dict.get(key, None)

    def _delete(self, key):
        self.db_dict.pop(key, None)

    def _set(self, key, value):
        self.db_dict[key] = value
