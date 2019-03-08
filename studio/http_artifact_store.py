from .tartifact_store import TartifactStore
from .util import download_file, upload_file
from . import logs


class HTTPArtifactStore(TartifactStore):
    def __init__(self, url,
                 timestamp=None,
                 compression=None,
                 verbose=logs.DEBUG):

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        self.url = url
        self.timestamp = timestamp

        super(HTTPArtifactStore, self).__init__(
            False,
            compression=compression,
            verbose=verbose)

    def _upload_file(self, key, local_path):
        upload_file(self.url, local_path, self.logger)

    def _download_file(self, key, local_path):
        download_file(self.url, local_path, self.logger)

    def _delete_file(self, key):
        raise NotImplementedError

    def _get_file_url(self, key):
        raise NotImplementedError

    def _get_file_timestamp(self, key):
        return self.timestamp

    def get_qualified_location(self, key):
        return self.endpoint + '/' + key
