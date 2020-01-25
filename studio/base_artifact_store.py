class BaseArtifactStore(object):

    def __init__(self):
        self.storage_client = None

    def set_storage_client(self, sclient):
        self.storage_client = sclient

    def get_storage_client(self):
        return self.storage_client

