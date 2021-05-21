import json
from studio.db_providers.keyvalue_provider import KeyValueProvider
from studio.storage.storage_handler_factory import StorageHandlerFactory
from studio.storage.storage_type import StorageType


class S3Provider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True):
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        factory: StorageHandlerFactory = StorageHandlerFactory.get_factory()
        self.meta_store = factory.get_handler(StorageType.storageS3, config)

        super().__init__(
            config,
            self.meta_store,
            blocking_auth)

    def _get(self, key, shallow=False):
        try:
            response = self.meta_store.client.list_objects(
                Bucket=self.bucket,
                Prefix=key,
                Delimiter='/',
                MaxKeys=1024*16
            )
        except Exception as exc:
            msg: str = "FAILED to list objects in bucket {0}: {1}"\
                .format(self.bucket, exc)
            self._report_fatal(msg)
            return None

        if response is None:
            return None

        if 'Contents' not in response.keys():
            return None

        key_count = len(response['Contents'])

        if key_count == 0:
            return None

        for key_item in response['Contents']:
            if 'Key' in key_item.keys() and key_item['Key'] == key:
                response = self.meta_store.client.get_object(
                    Bucket=self.bucket,
                    Key=key)
                return json.loads(response['Body'].read().decode("utf-8"))

        return None

    def _delete(self, key, shallow=True):
        self.logger.info("S3 deleting object: %s/%s", self.bucket, key)

        try:
            response = self.meta_store.client.delete_object(
                Bucket=self.bucket,
                Key=key)
        except Exception as exc:
            msg: str = "FAILED to delete object {0} in bucket {1}: {2}"\
                .format(key, self.bucket, exc)
            self.logger.info(msg)
            return

        reason = response['ResponseMetadata'] if response else "None"
        if response is None or\
            response['ResponseMetadata']['HTTPStatusCode'] != 204:
            msg: str = ('attempt to delete key {0} in bucket {1}' +
                       ' returned response {2}')\
                           .format(key, self.bucket, reason)
            self.logger.info(msg)

    def _set(self, key, value):
        try:
            response = self.meta_store.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(value))
        except Exception as exc:
            msg: str = "FAILED to write object {0} in bucket {1}: {2}"\
                .format(key, self.bucket, exc)
            self._report_fatal(msg)

        reason = response['ResponseMetadata'] if response else "None"
        if response is None or \
                response['ResponseMetadata']['HTTPStatusCode'] != 200:
            msg: str = ('attempt to write key {0} in bucket {1}' +
                       ' returned response {2}')\
                .format(key, self.bucket, reason)
            self._report_fatal(msg)
