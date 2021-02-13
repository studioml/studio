import os
import uuid
import time

from .storage_type import StorageType
from .util import get_temp_filename

# StorageHandler encapsulates the logic of basic storage operations
# for specific storage endpoint (S3, http, local etc.)
# together with access credentials for this endpoint.
class StorageHandler(object):
    def __init__(self, storage_type: StorageType,
                 logger,
                 measure_timestamp_diff=False,
                 compression=None):
        self.type = storage_type
        self.logger = logger
        self.compression = compression
        self._timestamp_shift = 0
        if measure_timestamp_diff:
            try:
                self._timestamp_shift = self._measure_timestamp_diff()
            except BaseException:
                self._timestamp_shift = 0

    def upload_file(self, key, local_path):
        raise NotImplementedError("Not implemented: upload_file")

    def download_file(self, key, local_path):
        raise NotImplementedError("Not implemented: download_file")

    def download_remote_path(self, remote_path, local_path):
        raise NotImplementedError("Not implemented: download_remote_path")

    def delete_file(self, key, shallow=True):
        raise NotImplementedError("Not implemented: delete_file")

    def get_file_url(self, key, method='GET'):
        raise NotImplementedError("Not implemented: get_file_url")

    def get_file_timestamp(self, key):
        raise NotImplementedError("Not implemented: get_file_timestamp")

    def get_qualified_location(self, key):
        raise NotImplementedError("Not implemented: get_qualified_location")

    def get_local_destination(self, remote_path: str):
        raise NotImplementedError("Not implemented: get_local_destination")

    def get_timestamp_shift(self):
        return self._timestamp_shift

    def cleanup(self):
        pass

    def _measure_timestamp_diff(self):
        max_diff = 60
        tmpfile = get_temp_filename() + '.txt'
        with open(tmpfile, 'w') as f:
            f.write('timestamp_diff_test')
        key = 'tests/' + str(uuid.uuid4())
        self.upload_file(key, tmpfile)
        remote_timestamp = self.get_file_timestamp(key)

        if remote_timestamp is not None:
            now_remote_diff = time.time() - remote_timestamp
            self.storage_handler.delete_file(key)
            os.remove(tmpfile)

            assert -max_diff < now_remote_diff and \
                now_remote_diff < max_diff, \
                "Timestamp difference is more than 60 seconds. " + \
                "You'll need to adjust local clock for caching " + \
                "to work correctly"

            return -now_remote_diff if now_remote_diff < 0 else 0

