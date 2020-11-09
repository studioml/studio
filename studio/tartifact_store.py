import os
import uuid

import time
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

from .artifact import Artifact
from . import logs
from .storage_handler import StorageHandler
from .util import compression_to_extension
from .util import get_temp_filename

from .base_artifact_store import BaseArtifactStore


class TartifactStore(BaseArtifactStore):

    def __init__(self, handler: StorageHandler,
                 measure_timestamp_diff=False,
                 compression=None,
                 verbose=logs.DEBUG):

        super().__init__()
        self.storage_handler = handler

        if measure_timestamp_diff:
            try:
                self.timestamp_shift = self._measure_timestamp_diff()
            except BaseException:
                self.timestamp_shift = 0
        else:
            self.timestamp_shift = 0

        self.compression = compression
        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

    def _measure_timestamp_diff(self):
        max_diff = 60
        tmpfile = get_temp_filename() + '.txt'
        with open(tmpfile, 'w') as f:
            f.write('timestamp_diff_test')
        key = 'tests/' + str(uuid.uuid4())
        self.storage_handler.upload_file(key, tmpfile)
        remote_timestamp = self.storage_handler.get_file_timestamp(key)

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

    def get_artifact_hash(
            self,
            artifact: Artifact,
            local_path=None):

        return artifact.get_hash(local_path)


    def put_artifact(
            self,
            artifact: Artifact,
            local_path=None):

        return artifact.upload(local_path)


    def get_artifact(
            self,
            artifact: Artifact,
            local_path=None,
            only_newer=True):

        return artifact.download(local_path, only_newer)


    def get_artifact_url(self, artifact: Artifact, method='GET', get_timestamp=False):

        return artifact.get_url(method=method, get_timestamp=get_timestamp)


    def delete_artifact(self, artifact: Artifact):
        artifact.delete()


    def stream_artifact(self, artifact: Artifact):

        return artifact.stream()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def get_immutable_artifact_key(arthash, compression=None):
    retval = "blobstore/" + arthash + ".tar" + \
             compression_to_extension(compression)
    return retval
