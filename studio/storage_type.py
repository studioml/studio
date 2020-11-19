from enum import Enum

class StorageType(Enum):
    storageHTTP = 1
    storageS3 = 2
    storageLocal = 3
    storageFirebase = 4
    storageDockerHub = 5
    storageSHub = 6

    storageInvalid = 99