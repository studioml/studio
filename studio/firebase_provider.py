from .keyvalue_provider import KeyValueProvider


class FirebaseProvider(KeyValueProvider):

    def __init__(self, db_config, blocking_auth=True, verbose=10, store=None):
        super(
            FirebaseProvider,
            self).__init__(
            db_config,
            blocking_auth,
            verbose,
            store)

    def _get(self, key, shallow=False):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.app.database().child(key_path).child(key_name)
            return dbobj.get(self.auth.get_token(), shallow=shallow).val() \
                if self.auth else dbobj.get(shallow=shallow).val()
        except Exception as err:
            self.logger.warn(("Getting key {} from a database " +
                              "raised an exception: {}").format(key, err))
            return None

    def _set(self, key, value):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.app.database().child(key_path)
            if self.auth:
                dbobj.update({key_name: value}, self.auth.get_token())
            else:
                dbobj.update({key_name: value})
        except Exception as err:
            self.logger.warn(("Putting key {}, value {} into a database " +
                              "raised an exception: {}")
                             .format(key, value, err))

    def _delete(self, key, token=None):
        dbobj = self.app.database().child(key)

        if self.auth:
            dbobj.remove(self.auth.get_token())
        else:
            dbobj.remove()
