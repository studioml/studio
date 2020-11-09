from enum import Enum

class StorageType(Enum):
    storageHTTP = 1
    storageS3 = 2
    storageDockerHub = 3
    storageSHub = 4

    storageInvalid = 99