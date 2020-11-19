from . import logs
from .model_setup import get_model_verbose_level
from .storage_type import StorageType
from .storage_handler import StorageHandler
from . import util

class HTTPStorageHandler(StorageHandler):
    def __init__(self, url,
                 timestamp=None,
                 compression=None):

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())

        self.url = url
        self.timestamp = timestamp

        super().__init__(StorageType.storageHTTP,
            self.logger,
            False,
            compression=compression)

    def upload_file(self, key, local_path):
        util.upload_file(self.url, local_path, self.logger)

    def download_file(self, key, local_path):
        util.download_file(self.url, local_path, self.logger)

    def delete_file(self, key):
        raise NotImplementedError

    def get_file_url(self, key):
        raise NotImplementedError

    def get_file_timestamp(self, key):
        return self.timestamp

    def get_qualified_location(self, key):
        return self.endpoint + '/' + key
