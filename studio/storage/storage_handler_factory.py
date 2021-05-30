from studio.util import logs
from typing import Dict

from studio.storage.http_storage_handler import HTTPStorageHandler
from studio.storage.local_storage_handler import LocalStorageHandler
from studio.storage.storage_setup import get_storage_verbose_level
from studio.storage.storage_handler import StorageHandler
from studio.storage.storage_type import StorageType
from studio.storage.s3_storage_handler import S3StorageHandler

_storage_factory = None

class StorageHandlerFactory:
    def __init__(self):
        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(get_storage_verbose_level())
        self.handlers_cache = dict()
        self.cleanup_at_exit: bool = True

    @classmethod
    def get_factory(cls):
        global _storage_factory
        if _storage_factory is None:
            _storage_factory = StorageHandlerFactory()
        return _storage_factory

    def set_cleanup_at_exit(self, value: bool):
        self.cleanup_at_exit = value

    def cleanup(self):
        if not self.cleanup_at_exit:
            return

        for _, handler in self.handlers_cache.items():
            if handler is not None:
                handler.cleanup()

    def get_handler(self, handler_type: StorageType,
                    config: Dict) -> StorageHandler:
        if handler_type == StorageType.storageS3:
            handler_id: str = S3StorageHandler.get_id(config)
            handler = self.handlers_cache.get(handler_id, None)
            if handler is None:
                handler = S3StorageHandler(config)
                self.handlers_cache[handler_id] = handler
            return handler
        if handler_type == StorageType.storageHTTP:
            handler_id: str = HTTPStorageHandler.get_id(config)
            handler = self.handlers_cache.get(handler_id, None)
            if handler is None:
                handler = HTTPStorageHandler(
                    config.get('endpoint', None),
                    config.get('credentials', None))
                self.handlers_cache[handler_id] = handler
            return handler
        if handler_type == StorageType.storageLocal:
            handler_id: str = LocalStorageHandler.get_id(config)
            handler = self.handlers_cache.get(handler_id, None)
            if handler is None:
                handler = LocalStorageHandler(config)
                self.handlers_cache[handler_id] = handler
            return handler
        self.logger("FAILED to get storage handler: unsupported type %s",
                    repr(handler_type))
        return None