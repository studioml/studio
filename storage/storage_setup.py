from storage.storage_handler_factory import StorageHandlerFactory
from storage.storage_handler import StorageHandler
from storage.storage_type import StorageType
from util.logs import INFO

DB_KEY = "database"
STORE_KEY = "store"

# Global dictionary which keeps Database Provider
# and Artifact Store objects created from experiment configuration.
_storage_setup = None

_storage_verbose_level = INFO

def setup_storage(db_provider, artifact_store):
    global _storage_setup
    _storage_setup = { DB_KEY: db_provider, STORE_KEY: artifact_store }

def get_storage_db_provider():
    global _storage_setup
    if _storage_setup is None:
        return None
    return _storage_setup.get(DB_KEY, None)

def get_storage_artifact_store():
    global _storage_setup
    if _storage_setup is None:
        return None
    return _storage_setup.get(STORE_KEY, None)

def reset_storage():
    global _storage_setup
    _storage_setup = None

def get_artifact_store(config) -> StorageHandler:
    storage_type: str = config['type'].lower()

    factory: StorageHandlerFactory = StorageHandlerFactory.get_factory()
    if storage_type == 's3':
        handler = factory.get_handler(StorageType.storageS3, config)
        return handler
    elif storage_type == 'local':
        handler = factory.get_handler(StorageType.storageLocal, config)
        return handler
    else:
        raise ValueError('Unknown storage type: ' + storage_type)

def get_storage_verbose_level():
    global _storage_verbose_level
    return _storage_verbose_level

def set_storage_verbose_level(level: int):
    global _storage_verbose_level
    _storage_verbose_level = level

def has_aws_credentials():
    artifact_store = get_storage_artifact_store()
    if artifact_store is None:
        return False
    storage_handler = artifact_store.get_storage_handler()
    if storage_handler.type == StorageType.storageS3:
        storage_client = storage_handler.get_client()
        return storage_client._request_signer._credentials is not None
    else:
        return False


