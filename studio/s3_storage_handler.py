import calendar

import os
from urllib.parse import urlparse
from boto3.s3.transfer import TransferConfig
from boto3.session import Session
import botocore
from botocore.client import Config
from botocore.handlers import set_list_objects_encoding_type_url
import re

from . import logs
from . import util
from .credentials import Credentials, AWS_TYPE
from .storage_handler import StorageHandler
from .storage_type import StorageType
from .model_setup import get_model_verbose_level

class S3StorageHandler(StorageHandler):
    def __init__(self, config,
                 measure_timestamp_diff=False,
                 compression=None):
        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())
        self.credentials: Credentials =\
            Credentials.getCredentials(config)

        self.endpoint = config.get('endpoint', None)

        if self.credentials is None:
            msg: str = "NO CREDENTIALS provided for {0}."\
                .format(self.endpoint)
            self._report_fatal(msg)

        if self.credentials.get_type() != AWS_TYPE:
            msg: str = "EXPECTED aws credentials for {0}: {1}"\
                .format(self.endpoint, repr(self.credentials.to_dict()))
            self._report_fatal(msg)

        aws_key: str = self.credentials.get_key()
        aws_secret_key = self.credentials.get_secret_key()
        session = Session(aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret_key,
            region_name=config.get('region'))

        session.events.unregister('before-parameter-build.s3.ListObjects',
                          set_list_objects_encoding_type_url)

        self.client = session.client(
            's3',
            endpoint_url=self.endpoint,
            config=Config(signature_version='s3v4'))

        if compression is None:
            compression = config.get('compression')

        self.cleanup_bucket = config.get('cleanup_bucket', False)
        if isinstance(self.cleanup_bucket, str):
            self.cleanup_bucket = self.cleanup_bucket.lower() == 'true'

        self.endpoint = self.client._endpoint.host

        self.bucket = config['bucket']
        try:
            buckets = self.client.list_buckets()
        except Exception as exc:
            msg: str = "FAILED to list buckets for {0}: {1}"\
                .format(self.endpoint, exc)
            self._report_fatal(msg)

        if self.bucket not in [b['Name'] for b in buckets['Buckets']]:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception as exc:
                msg: str = "FAILED to create bucket {0} for {1}: {2}"\
                    .format(self.bucket, self.endpoint, exc)
                self._report_fatal(msg)

        super().__init__(StorageType.storageS3,
            self.logger,
            measure_timestamp_diff,
            compression=compression)

    def _not_found(self, response):
        try:
            return response['Error']['Code'] == '404'
        except Exception:
            return False

    def upload_file(self, key, local_path):
        if not os.path.exists(local_path):
            self.logger.debug(
                "Local path {0} does not exist. SKIPPING upload to {1}/{2}"
                    .format(local_path, self.bucket, key))
            return False
        try:
            config = TransferConfig(multipart_threshold=2 * 1024 * 1024 * 1024)
            with open(local_path, 'rb') as data:
                self.client.upload_fileobj(data, self.bucket, key, Config=config)
            return True
        except Exception as exc:
            self._report_fatal("FAILED to upload file {0} to {1}/{2}: {3}"
                               .format(local_path, self.bucket, key, exc))
            return False

    def download_file(self, key, local_path):
        try:
            head, _ = os.path.split(local_path)
            if head is not None:
                os.makedirs(head, exist_ok=True)
            self.client.download_file(self.bucket, key, local_path)
            return True
        except botocore.exceptions.ClientError as exc:
            if self._not_found(exc.response):
                self.logger.debug(
                    "No key found: {0}/{1}. SKIPPING download to {2}"
                    .format(self.bucket, key, local_path))
            else:
                self._report_fatal("FAILED to download file {0} from {1}/{2}: {3}"
                                   .format(local_path, self.bucket, key, exc))
            return False
        except Exception as exc:
            self._report_fatal("FAILED to download file {0} from {1}/{2}: {3}"
                               .format(local_path, self.bucket, key, exc))
            return False

    def download_remote_path(self, remote_path, local_path):
        # remote_path is full S3-formatted file reference
        if remote_path.endswith('/'):
            _, _, key = util.parse_s3_path(remote_path[:-1])
            return self._download_dir(key+'/', local_path)
        else:
            _, _, key = util.parse_s3_path(remote_path)
            return self.download_file(key, local_path)

    def _download_dir(self, key, local):
        self.logger.debug("s3 download dir.: bucket: {0} key: {1} to {2}"
                          .format(self.bucket, key, local))

        success: bool = True
        paginator = self.client.get_paginator('list_objects')
        for result in paginator.paginate(
                Bucket=self.bucket,
                Delimiter='/',
                Prefix=key):
            if result.get('CommonPrefixes') is not None:
                for subdir in result.get('CommonPrefixes'):
                    prefix: str = subdir.get('Prefix')
                    local_prefix: str = re.sub('^'+key, '', prefix)
                    dir_success: bool = self._download_dir(
                        prefix,
                        os.path.join(local, local_prefix)
                    )
                    success = success and dir_success

            if result.get('Contents') is not None:
                for file in result.get('Contents'):
                    file_key = file.get('Key')

                    local_dir_path: str = local
                    if not os.path.exists(local_dir_path):
                        os.makedirs(local_dir_path)

                    local_path = os.path.join(local, re.sub('^'+key, '', file_key))
                    self.logger.debug(
                            'Downloading {0}/{1} to {2}'
                                .format(self.bucket, file_key, local_path))
                    success = self.download_file(file_key, local_path)\
                              and success
        return success

    def get_local_destination(self, remote_path: str):
        if remote_path.endswith('/'):
            _, _, key = util.parse_s3_path(remote_path[:-1])
            parts = key.split('/')
            return parts[len(parts)-1], None
        else:
            _, _, key = util.parse_s3_path(remote_path)
            parts = key.split('/')
            return parts[len(parts)-2], parts[len(parts)-1]

    def delete_file(self, key, shallow=True):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def cleanup(self):
        if not self.cleanup_bucket:
            return

        # Delete current S3 bucket completely.
        prefix: str = ''
        is_truncated: bool = True
        max_keys = 1000
        key_marker = None

        while is_truncated:
            if key_marker is None:
                version_list = self.client.list_object_versions(
                    Bucket=self.bucket,
                    MaxKeys=max_keys,
                    Prefix=prefix)
            else:
                version_list = self.client.list_object_versions(
                    Bucket=self.bucket,
                    MaxKeys=max_keys,
                    Prefix=prefix,
                    KeyMarker=key_marker)

            if version_list is None:
                break

            try:
                objects = []
                versions = version_list.get('Versions', [])
                for v in versions:
                    objects.append({'VersionId': v['VersionId'], 'Key': v['Key']})
                response = self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={'Objects': objects})
            except Exception as exc:
                self.logger.error("FAILED to delete objects in bucket: %s - %s",
                                  self.bucket, exc)

            try:
                objects = []
                delete_markers = version_list.get('DeleteMarkers', [])
                for d in delete_markers:
                    objects.append({'VersionId': d['VersionId'], 'Key': d['Key']})
                response = self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={'Objects': objects})
            except Exception as exc:
                self.logger.error("FAILED to delete markers in bucket: %s - %s",
                                  self.bucket, exc)

            is_truncated = version_list.get('IsTruncated', False)
            key_marker = version_list.get('NextKeyMarker', None)

        # Now we can delete bucket itself:
        try:
            self.client.delete_bucket(Bucket=self.bucket)
        except Exception as exc:
            self.logger.error("FAILED to delete bucket: %s - %s",
                      self.bucket, exc)

    def get_file_url(self, key, method='GET'):
        if method == 'GET':
            return self.client.generate_presigned_url(
                'get_object', Params={'Bucket': self.bucket, 'Key': key})
        elif method == 'PUT':
            return self.client.generate_presigned_url(
                'put_object', Params={'Bucket': self.bucket, 'Key': key})
        else:
            raise ValueError('Unknown method {0} in get_file_url()'.format(method))

    def get_file_timestamp(self, key):
        time_updated = False
        try:
            obj = self.client.head_object(Bucket=self.bucket, Key=key)
            time_updated = obj.get('LastModified', None)
        except botocore.exceptions.ClientError as exc:
            if self._not_found(exc.response):
                self.logger.debug(
                    "No key found: {0}/{1}. Cannot get timestamp."
                        .format(self.bucket, key))
            else:
                self.logger.error("FAILED to get timestamp for S3 object {0}/{1}"
                        .format(self.bucket, key))
            return None
        except BaseException:
            self.logger.error("FAILED to get timestamp for S3 object {0}/{1}"
                              .format(self.bucket, key))
            return None

        if time_updated:
            timestamp = calendar.timegm(time_updated.timetuple())
            return timestamp
        else:
            return None

    def get_qualified_location(self, key):
        url = urlparse(self.endpoint)
        location: str = 's3://' + url.netloc + '/' + self.bucket + '/' + key

        return location

    def get_bucket(self):
        return self.bucket

    def get_client(self):
        return self.client

    def _report_fatal(self, msg: str):
        util.report_fatal(msg, self.logger)
