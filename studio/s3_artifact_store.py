import logging
import calendar
from urlparse import urlparse

try:
    import boto3
except BaseException:
    boto3 = None

from tartifact_store import TartifactStore
logging.basicConfig()


class S3ArtifactStore(TartifactStore):
    def __init__(self, config, verbose=10, measure_timestamp_diff=True):
        self.logger = logging.getLogger('S3ArtifactStore')
        self.logger.setLevel(verbose)

        if 'aws_access_key' in config.keys():
            access_key = config['aws_access_key']
            secret_key = config['aws_secret_key']
            self.client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)

        else:
            self.client = boto3.client(service_name='s3')
        self.endpoint = self.client._endpoint.host

        self.bucket = config['bucket']
        buckets = self.client.list_buckets()

        if self.bucket not in [b['Name'] for b in buckets['Buckets']]:
            self.client.create_bucket(Bucket=self.bucket)

        super(S3ArtifactStore, self).__init__(measure_timestamp_diff)

    def _upload_file(self, key, local_path):
        self.client.upload_file(local_path, self.bucket, key)

    def _download_file(self, key, local_path):
        self.client.download_file(self.bucket, key, local_path)

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
            raise ValueError('Unknown method ' + method)

    def _get_file_post(self, key):
        return self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key)

    def _get_file_timestamp(self, key):
        obj = boto3.resource('s3').Object(self.bucket, key)

        try:
            time_updated = obj.last_modified
        except BaseException as e:
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
