from .artifact import Artifact
from . import logs
from .model_setup import get_model_verbose_level
from .storage_handler import StorageHandler

class TartifactStore:

    def __init__(self, handler: StorageHandler,
                 logger=None):

        super().__init__()
        self.storage_handler = handler

        self.logger = logger
        if self.logger is None:
            self.logger = logs.getLogger(self.__class__.__name__)
            self.logger.setLevel(get_model_verbose_level())

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

    def cleanup(self):
        if self.storage_handler is not None:
            self.storage_handler.cleanup()

    def stream_artifact(self, artifact: Artifact):

        return artifact.stream()

    def get_storage_handler(self):
        return self.storage_handler

    def get_qualified_location(self, key: str):
        if self.storage_handler is not None:
            return self.storage_handler.get_qualified_location(key)
        else:
            return None

