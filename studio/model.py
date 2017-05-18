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
        return self.db.get(key)

    def __setitem__(self, key, value):
        return self.db.post(key, value)



class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass
