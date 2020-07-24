import botocore
import json
import re
from .keyvalue_provider import KeyValueProvider
from .s3_artifact_store import S3ArtifactStore


class S3Provider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = S3ArtifactStore(config, verbose)

        super(S3Provider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

    def _get(self, key, shallow=False):
        response = self.meta_store.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=key,
            Delimiter='/'
        )

        if response['KeyCount'] == 0:
            return None

        if response['KeyCount'] == 1 and \
            'Contents' in response.keys() and \
                response['Contents'][0]['Key'] == key:
            response = self.meta_store.client.get_object(
                Bucket=self.bucket,
                Key=key)
            return json.loads(response['Body'].read().decode("utf-8"))
        else:
            if response['KeyCount'] > 1:
                assert shallow, \
                    'multiple-object reads ' + \
                    'are not supported for s3 provider yet {} {}'.format(
                        key, response)

            keys = []
            keys += [c['Key'] for c in response.get('Contents', [])]
            keys += [c['Prefix'][:-1]
                     for c in response.get('CommonPrefixes', [])]
            suffixes = [re.sub('^' + key, '', k) for k in keys]

            return suffixes

    def _delete(self, key):
        self.logger.info("S3 deleting object: {0}/{1}".format(self.bucket, key))

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
