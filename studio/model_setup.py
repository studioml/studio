
DB_KEY = "database"
STORE_KEY = "store"

# Global dictionary which keeps Database Provider
# and Artifact Store objects created from experiment configuration.
_model_setup = None

def setup_model(db_provider, artifact_store):
    global _model_setup
    _model_setup = { DB_KEY: db_provider, STORE_KEY: artifact_store }

def get_model_db_provider():
    global _model_setup
    if _model_setup is None:
        return None
    return _model_setup.get(DB_KEY, None)

def get_model_artifact_store():
    global _model_setup
    if _model_setup is None:
        return None
    return _model_setup.get(STORE_KEY, None)

def reset_model():
    global _model_setup
    _model_setup = None

