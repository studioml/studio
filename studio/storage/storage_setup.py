from studio.storage.storage_handler import StorageHandler
from studio.storage.storage_type import StorageType
from studio.util.logs import INFO

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

def get_storage_verbose_level():
    global _storage_verbose_level
    return _storage_verbose_level

def set_storage_verbose_level(level: int):
    global _storage_verbose_level
    _storage_verbose_level = level


