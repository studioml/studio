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
import time

import fs_tracker
from auth import FirebaseAuth

class Experiment(object):
    """Experiment information."""

    def __init__(self, key, filename, args, pythonenv, 
                    project=None,
                    workspace_path='.', 
                    model_dir=None, 
                    status='waiting', 
                    time_added=None,
                    time_started=None,
                    time_last_checkpoint=None,
                    time_finished=None):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project
        self.workspace_path = workspace_path
        self.model_dir = model_dir if model_dir else fs_tracker.get_model_directory(key)
        self.status = status
        self.time_added = time_added
        self.time_started = time_started
        self.time_last_checkpoint = time_last_checkpoint
        self.time_finished = time_finished

    def time_to_string(self, timestamp):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    

def create_experiment(filename, args, experiment_name=None, project=None):
     key = str(uuid.uuid4()) if not experiment_name else experiment_name
     packages = [p._key + '==' + p._version for p in pip.pip.get_installed_distributions(local_only=True)]
     return Experiment(
        key=key, filename=filename, args=args, pythonenv=packages, project=project)


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
            self.__setitem__(self._get_user_keybase() + "email", self.auth.get_user_email())
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

    def _get_user_keybase(self, userid=None):
        if not userid:
            if not self.auth:
                userid = 'guest'
            else:
                userid = self.auth.get_user_id()

        return "users/" + userid + "/" 

    def _get_experiments_keybase(self, userid=None):
        return self._get_user_keybase(userid) + "experiments/"
    
    def _get_projects_keybase(self):
        return "projects/"
         

    def add_experiment(self, experiment):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'
        self.__setitem__(self._get_experiments_keybase() + experiment.key, experiment.__dict__)   
        self._save_dir(experiment.workspace_path, self._get_experiments_keybase() + experiment.key + "/workspace/")

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() + experiment.project + "/" + experiment.key + "/userId",  self.auth.get_user_id())

    def start_experiment(self, experiment):
        experiment.time_started = time.time()
        experiment.status = 'running'
        self.__setitem__(self._get_experiments_keybase() + experiment.key + "/status", "running")
        self.__setitem__(self._get_experiments_keybase() + experiment.key + "/time_started", experiment.time_started)
        self.checkpoint_experiment(experiment)
        
    def finish_experiment(self, experiment):
        self.checkpoint_experiment(experiment)
        experiment.status = 'finished'
        experiment.time_finished = time.time()
        self.__setitem__(self._get_experiments_keybase() + experiment.key + "/status", "finished")
        self.__setitem__(self._get_experiments_keybase() + experiment.key + "/time_finished", experiment.time_finished)
      

    def checkpoint_experiment(self, experiment):
        self._save_dir(experiment.workspace_path, self._get_experiments_keybase() + experiment.key + "/workspace_latest/")
        self._save_dir(experiment.model_dir, self._get_experiments_keybase() + experiment.key + "/modeldir/")
        self.__setitem__(self._get_experiments_keybase() + experiment.key + "/time_last_checkpoint", time.time())

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
            filename=data['filename'],
            args=data['args'] if 'args' in data.keys() else None,
            pythonenv=data['pythonenv'],
            project=data['project'] if 'project' in data.keys() else None,
            status=data['status'],
            time_added=data['time_added'],
            time_started=data['time_started'] if 'time_started' in data.keys() else None,
            time_last_checkpoint=data['time_last_checkpoint'] if 'time_last_checkpoint' in data.keys() else None,
            time_finished=data['time_finished'] if 'time_finished' in data.keys() else None
        )

    def get_experiment(self, key, user_id=None):
        data = self.__getitem__(self._get_experiments_keybase(user_id) + key)
        assert data, "data at path %s not found! " % (self._get_experiments_keybase(user_id) + key)
        return self._experiment(key, data)

    def get_user_experiments(self, userid=None):
        # TODO: Add users and filtering
        values = self[self._get_experiments_keybase(userid)]
        if not values:
            values = {}

        experiments = []
        for key, data in values.iteritems():
            experiments.append(self._experiment(key, data))
        return experiments
    
    def get_projects(self):
        return self.__getitem__(self._get_projects_keybase())

    def get_users(self):
        return self.__getitem__('users/')

    def get_myuser_id(self):
        return 'guest' if not self.auth else self.auth.get_user_id()


class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass

    def add_experiment(self, experiment):
        raise NotImplementedError()

    def start_experiment(self, experiment):
        raise NotImplementedError()

    def finish_experiment(self, experiment):
        raise NotImplementedError()

    def get_experiment(self, key):
        raise NotImplementedError()

    def get_user_experiments(self, user):
        raise NotImplementedError()

    def get_projects(self):
        raise NotImplementedError()

    def get_users(self):
        raise NotImplementedError()

    def get_myuser_id(self):
        raise NotImplementedError()

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()


def get_default_config():
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
