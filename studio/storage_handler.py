from .storage_type import StorageType

class StorageHandler(object):
    def __init__(self, type: StorageType, logger):
        self.type = type
        self.logger = logger

    def upload_file(self, key, local_path):
        raise NotImplementedError("Not implemented: upload_file")

    def download_file(self, key, local_path):
        raise NotImplementedError("Not implemented: download_file")

    def delete_file(self, key):
        raise NotImplementedError("Not implemented: delete_file")

    def get_file_url(self, key, method='GET'):
        raise NotImplementedError("Not implemented: get_file_url")

    def get_file_timestamp(self, key):
        raise NotImplementedError("Not implemented: get_file_timestamp")
