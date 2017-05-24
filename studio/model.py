"""Data providers."""

import os
import pip
import uuid

import yaml
import pyrebase
import logging
import hashlib
import base64
import zlib

import fs_tracker
from auth import FirebaseAuth

class Experiment(object):
    """Experiment information."""

    def __init__(self, key, filename, args, pythonenv, workspace_path='.', model_dir=None):
        self.key = key
        self.filename = filename
        self.args = args
        self.pythonenv = pythonenv
        self.workspace_path = workspace_path
        self.model_dir = model_dir if model_dir else fs_tracker.get_model_directory(key)
    

def create_experiment(filename, args, experiment_name = None):
     key = str(uuid.uuid4()) if not experiment_name else experiment_name
     packages = [p._key + '==' + p._version for p in pip.pip.get_installed_distributions(local_only=True)]
     return Experiment(
        key=key, filename=filename, args=args, pythonenv=packages)


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, database_config):
        guest = database_config['guest'] if 'guest' in database_config.keys() else False
        app = pyrebase.initialize_app(database_config)
        self.db = app.database()
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(10)

        if not guest:
            self.auth = FirebaseAuth(app)
        else:
            self.auth = None

        #self.db = firebase.FirebaseApplication(host, auth)

    def __getitem__(self, key):
        splitKey = key.split('/')
        key_path = '/'.join(splitKey[:-1])
        key_name = splitKey[-1]
        dbobj = self.db.child(key_path).child(key_name)
        return dbobj.get(self.auth.get_token()).val() if self.auth else dbobj.get().val()

    def __setitem__(self, key, value):
        splitKey = key.split('/')
        key_path = '/'.join(splitKey[:-1])
        key_name = splitKey[-1]
        dbobj = self.db.child(key_path)
        if self.auth:
            dbobj.update( {key_name: value}, self.auth.get_token())
        else:
            dbobj.update( {key_name: value})

    def _delete(self, key):
        splitKey = key.split('/')
        key_path = '/'.join(splitKey[:-1])
        key_name = splitKey[-1]
        dbobj = self.db.child(key)

        if self.auth:
            dbobj.remove(self.auth.get_token())
        else:
            dbobj.remove()


    def _get_experiments_keybase(self):
            return "users/" + (self.auth.get_user_id() if self.auth else 'guest') + "/experiments/"
         


    def add_experiment(self, experiment):
        self._delete(self._get_experiments_keybase() + experiment.key)
        self.__setitem__(self._get_experiments_keybase() + experiment.key,
            {
                "args": [experiment.filename] + experiment.args,
                "pythonenv": experiment.pythonenv
            })
        self._save_dir(experiment.workspace_path, self._get_experiments_keybase() + experiment.key + "/workspace/")
     

    def checkpoint_experiment(self, experiment):
        self._save_dir(experiment.workspace_path, self._get_experiments_keybase() + experiment.key + "/workspace_latest/")
        self._save_dir(experiment.model_dir, self._get_experiments_keybase() + experiment.key + "/modeldir/")

    def _save_dir(self, local_folder, key_base):
        self.logger.debug("saving local folder %s to key_base %s " % (local_folder, key_base))
        for root, dirs, files in os.walk(local_folder, topdown=False):
            for name in files:
                full_file_name = os.path.join(root, name)
                self.logger.debug("Saving " + full_file_name)
                with open(full_file_name, 'rb') as f:
                    data = f.read()
                    sha = hashlib.sha256(data).hexdigest()
                    self[key_base + sha + "/data"] = base64.b64encode(zlib.compress(bytes(data)))
                    self[key_base + sha + "/name"] = name

        self.logger.debug("Done saving")



    def _experiment(self, key, data):
        return Experiment(
            key=key,
            filename=data['args'][0],
            args=data['args'][1:],
            pythonenv=data['pythonenv']
        )

    def get_experiment(self, key):
        data = self.__getitem__(self._get_experiments_keybase() + key)
        return self._experiment(key, data)

    def get_user_experiments(self, user):
        # TODO: Add users and filtering
        values = self[self._get_experiments_keybase()]
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

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()


def get_default_config():
    print(os.path.dirname(os.path.realpath(__file__)))
    config_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "default_config.yaml")
    with open(config_file) as f:
        return yaml.load(f)


def get_db_provider(config=None):
    if not config:
        config = get_default_config()
    assert 'database' in config.keys()
    db_config = config['database']
    assert db_config['type'].lower() == 'firebase'.lower()
    return FirebaseProvider(db_config)
