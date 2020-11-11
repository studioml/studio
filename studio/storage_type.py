from enum import Enum

class StorageType(Enum):
    storageHTTP = 1
    storageS3 = 2
    storageLocal = 3
    storageDockerHub = 4
    storageSHub = 5

    storageInvalid = 99