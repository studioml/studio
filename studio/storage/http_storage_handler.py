import os
from urllib.parse import urlparse
from typing import Dict
from studio.util import logs
from studio.credentials.credentials import Credentials
from studio.storage.storage_setup import get_storage_verbose_level
from studio.storage.storage_type import StorageType
from studio.storage.storage_handler import StorageHandler
from studio.storage import storage_util

class HTTPStorageHandler(StorageHandler):
    def __init__(self, remote_path, credentials_dict,
                 timestamp=None,
                 compression=None):

        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(get_storage_verbose_level())

        self.url = remote_path
        self.timestamp = timestamp

        parsed_url = urlparse(self.url)
        self.scheme = parsed_url.scheme
        self.endpoint = parsed_url.netloc
        self.path = parsed_url.path
        self.credentials = Credentials(credentials_dict)

        super().__init__(StorageType.storageHTTP,
            self.logger,
            False,
            compression=compression)

    def upload_file(self, key, local_path):
        storage_util.upload_file(self.url, local_path, self.logger)

    def download_file(self, key, local_path):
        return storage_util.download_file(self.url, local_path, self.logger)

    def download_remote_path(self, remote_path, local_path):
        head, _ = os.path.split(local_path)
        if head is not None:
            os.makedirs(head, exist_ok=True)
        return storage_util.download_file(remote_path, local_path, self.logger)

    @classmethod
    def get_id(cls, config: Dict) -> str:
        endpoint = config.get('endpoint', None)
        if endpoint is None:
            return None
        creds: Credentials = Credentials.get_credentials(config)
        creds_fingerprint = creds.get_fingerprint() if creds else ''
        return '[http]{0}::{1}'.format(endpoint, creds_fingerprint)

    def get_local_destination(self, remote_path: str):
        parsed_url = urlparse(remote_path)
        parts = parsed_url.path.split('/')
        return None, parts[len(parts)-1]

    def delete_file(self, key, shallow=True):
        raise NotImplementedError

    def get_file_url(self, key):
        return self.url

    def get_file_timestamp(self, key):
        return self.timestamp

    def get_qualified_location(self, key):
        return self.url
