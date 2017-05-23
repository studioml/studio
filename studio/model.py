"""Data providers."""

try:
    from firebase import firebase
except ImportError:
    firebase = None


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, host, secret, email=None):
        auth = firebase.FirebaseAuthentication(secret, email)
        self.db = firebase.FirebaseApplication(host, auth)

    def __getitem__(self, key):
        splitKey = key.split('/')
        keyPath = '/'.join(splitKey[:-1])
        keyName = splitKey[-1]
        return self.db.get(keyPath, keyName)

    def __setitem__(self, key, value):
        splitKey = key.split('/')
        keyPath = '/'.join(splitKey[:-1])
        keyName = splitKey[-1]
        return self.db.patch(keyPath, {keyName: value})

    def delete(self, key):
        splitKey = key.split('/')
        keyPath = '/'.join(splitKey[:-1])
        keyName = splitKey[-1]
        self.db.delete(keyPath, keyName)



class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass
