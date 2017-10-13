import json
from .keyvalue_provider import KeyValueProvider
from .s3_artifact_store import S3ArtifactStore


class S3Provider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        super(
            S3Provider,
            self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = S3ArtifactStore(config, verbose)

        super(S3Provider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

    def _get(self, key, shallow=False):
        response = self.meta_store.client.get_object(
            Bucket=self.bucket,
            Key=key)

        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            return json.loads(response['Body'].read())

        elif response['ResponseMetadata']['HTTPStatusCode'] == 404:
            return None
        else:
            raise ValueError(
                'attempt to read key {} returned response {}'
                .format(key, response['ResponseMetadata']))

    def _delete(self, key):
        response = self.meta_store.client.delete_object(
            Bucket=self.bucket,
            Key=key)

        if response['ResponseMetadata']['HTTPStatusCode'] != 204:
            raise ValueError(
                ('attempt to delete write key {} ' +
                 'returned response {}')
                .format(key, response['ResponseMetadata']))

    def _set(self, key, value):
        response = self.meta_store.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(value))

        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise ValueError(
                ('attempt to read write key {}  with value {} ' +
                 'returned response {}')
                .format(key, value, response['ResponseMetadata']))
