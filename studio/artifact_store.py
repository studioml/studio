from firebase_artifact_store import FirebaseArtifactStore
from gcloud_artifact_store import GCloudArtifactStore


def get_artifact_store(config, blocking_auth=True, verbose=10):
    if config['type'].lower() == 'firebase':
        return FirebaseArtifactStore(
            config, blocking_auth=blocking_auth, verbose=verbose)
    elif config['type'].lower() == 'gcloud':
        return GCloudArtifactStore(config, verbose=verbose)
    else:
        raise ValueError('Unknown storage type: ' + config['type'])
