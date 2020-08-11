import calendar

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

try:
    import boto3
except ImportError:
    boto3 = None

from .tartifact_store import TartifactStore
from . import logs

class S3ArtifactStore(TartifactStore):
    def __init__(self, config,
                 verbose=10,
                 measure_timestamp_diff=False,
                 compression=None):
        self.client = boto3.client(
            's3',
            aws_access_key_id=config.get('aws_access_key'),
            aws_secret_access_key=config.get('aws_secret_key'),
            endpoint_url=config.get('endpoint'),
            region_name=config.get('region'))

        if compression is None:
            compression = config.get('compression')

        self.endpoint = self.client._endpoint.host

        self.bucket = config['bucket']
        buckets = self.client.list_buckets()

        if self.bucket not in [b['Name'] for b in buckets['Buckets']]:
            self.client.create_bucket(
                Bucket=self.bucket
            )
        super(S3ArtifactStore, self).__init__(
            measure_timestamp_diff,
            compression=compression,
            verbose=verbose)

        self.set_storage_client(self.client)


    def _upload_file(self, key, local_path):
        try:
            self.client.upload_file(local_path, self.bucket, key)
        except Exception as exc:
            self._report_fatal("FAILED to upload file {0} to {1}/{2}: {3}"
                               .format(local_path, self.bucket, key, exc))

    def _download_file(self, key, local_path, bucket=None):
        bucket = bucket or self.bucket
        try:
            self.client.download_file(bucket, key, local_path)
        except Exception as exc:
            self._report_fatal("FAILED to download file {0} from {1}/{2}: {3}"
                               .format(local_path, self.bucket, key, exc))


    def _delete_file(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def _get_file_url(self, key, method='GET'):
        if method == 'GET':
            return self.client.generate_presigned_url(
                'get_object', Params={'Bucket': self.bucket, 'Key': key})
        elif method == 'PUT':
            return self.client.generate_presigned_url(
                'put_object', Params={'Bucket': self.bucket, 'Key': key})
        else:
            raise ValueError('Unknown method {0} in get_file_url()'.format(method))

    def _get_file_post(self, key):
        return self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key)

    def _get_file_timestamp(self, key):

        try:
            obj = self.client.head_object(Bucket=self.bucket, Key=key)
            time_updated = obj.get('LastModified', None)
        except BaseException:
            return None

        if time_updated:
            timestamp = calendar.timegm(time_updated.timetuple())
            return timestamp
        else:
            return None

    def get_qualified_location(self, key):
        url = urlparse(self.endpoint)
        return 's3://' + url.netloc + '/' + self.bucket + '/' + key

    def get_bucket(self):
        return self.bucket
