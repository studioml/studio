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
        super(GSProvider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)


    def _get(self, key):
        try:
            return json.loads(
                self.meta_store._get_bucket_obj() \
                    .blob(key).download_as_string())
        except:
            return None

    def _delete(self, key):
        self.meta_store._delete_file(key)

    def _set(self, key, value):
        self.meta_store._get_bucket_obj().blob(key) \
            .upload_from_string(json.dumps(value))
