import os
from urllib.parse import urlparse
from . import logs, util
from .credentials import Credentials
from .model_setup import get_model_verbose_level
from .storage_type import StorageType
from .storage_handler import StorageHandler

class HTTPStorageHandler(StorageHandler):
    def __init__(self, remote_path, credentials_dict,
                 timestamp=None,
                 compression=None):

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())

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
        util.upload_file(self.url, local_path, self.logger)

    def download_file(self, key, local_path):
        return util.download_file(self.url, local_path, self.logger)

    def download_remote_path(self, remote_path, local_path):
        head, _ = os.path.split(local_path)
        if head is not None:
            os.makedirs(head, exist_ok=True)
        return util.download_file(remote_path, local_path, self.logger)

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
