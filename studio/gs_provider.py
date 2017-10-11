import boto3
import json
from .keyvalue_provider import KeyValueProvider
from .gcloud_artifact_store import GCloudArtifactStore


class GSProvider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        super(
            GSProvider,
            self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = GCloudArtifactStore(config, verbose)

        super(GSProvider, self).__init__(config, verbose)

    def _get(self, key):
        return json.loads(
            self.meta_store.get_bucket().blob(key).download_as_string())

    def _delete(self, key):
        self.meta_store._delete_file(key)

    def _set(self, key, value):
        self.meta_store.get_bucket().blob(key) \
            .upload_from_string(json.dumps(value))
