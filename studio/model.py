"""Data providers."""

try:
    from firebase import firebase
except ImportError:
    firebase = None


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, host, key):
        self.db = firebase.FirebaseApplication(host, key)

    def auth(self, username):
        # TODO: implement auth
        pass


class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass
