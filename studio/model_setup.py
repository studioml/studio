
DB_KEY = "database"
STORE_KEY = "store"

# Global dictionary which keeps Database Provider
# and Artifact Store objects created from experiment configuration.
_model_setup = None

def setup_model(db_provider, artifact_store):
    _model_setup = { DB_KEY: db_provider, STORE_KEY: artifact_store }

def get_db_provider():
    if _model_setup is None:
        return None
    return _model_setup.get(DB_KEY, None)

def get_artifact_store():
    if _model_setup is None:
        return None
    return _model_setup.get(STORE_KEY, None)
