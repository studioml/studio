"""Data providers."""

import os
import pip
import uuid
import yaml

try:
    from firebase import firebase
except ImportError:
    firebase = None


class Experiment(object):
    """Experiment information."""

    def __init__(self, key, filename, args, pythonenv):
        self.key = key
        self.filename = filename
        self.args = args
        self.pythonenv = pythonenv


def create_experiment(filename, args, experiment_name = None):
     key = str(uuid.uuid4()) if not experiment_name else experiment_name
     packages = [p._key + '==' + p._version for p in pip.pip.get_installed_distributions(local_only=True)]
     return Experiment(
        key=key, filename=filename, args=args, pythonenv=packages)


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

    def add_experiment(self, experiment):
        self.db.patch(
            "experiments/" + experiment.key,
            {
                "args": [experiment.filename] + experiment.args,
                "pythonenv": experiment.pythonenv
            })

    def _experiment(self, key, data):
        return Experiment(
            key=key,
            filename=data['args'][0],
            args=data['args'][1:],
            pythonenv=data['pythonenv']
        )

    def get_experiment(self, key):
        data = self.db.get("experiments", key)
        return self._experiment(key, data)

    def get_user_experiments(self, user):
        # TODO: Add users and filtering
        values = self.db.get(".", "experiments")
        experiments = []
        for key, data in values.iteritems():
            experiments.append(self._experiment(key, data))
        return experiments


class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass

    def add_experiment(self, experiment):
        raise NotImplementedError()

    def get_experiment(self, key):
        raise NotImplementedError()

    def get_user_experiments(self, user):
        raise NotImplementedError()

    def delete(self, key):
        raise NotImplementedError()


def get_default_config():
    print(os.path.dirname(os.path.realpath(__file__)))
    config_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "defaultConfig.yaml")
    with open(config_file) as f:
        return yaml.load(f)


def get_db_provider(config=None):
    if not config:
        config = get_default_config()
    assert 'database' in config.keys()
    db_config = config['database']
    assert db_config['type'].lower() == 'firebase'.lower()
    return FirebaseProvider(db_config['url'], db_config['secret'])
