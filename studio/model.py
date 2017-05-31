"""Data providers."""

import os
import pip
import uuid

import yaml
import pyrebase
import logging
import time
import glob
import tempfile
import re
from threading import Thread
import subprocess

from tensorflow.contrib.framework.python.framework import checkpoint_utils

import fs_tracker
from auth import FirebaseAuth

logging.basicConfig()


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
                 time_finished=None,
                 info={}):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project
        self.workspace_path = workspace_path
        self.model_dir = model_dir if model_dir \
            else fs_tracker.get_model_directory(key)

        self.status = status
        self.time_added = time_added
        self.time_started = time_started
        self.time_last_checkpoint = time_last_checkpoint
        self.time_finished = time_finished
        self.info = info


def create_experiment(filename, args, experiment_name=None, project=None):
    key = str(uuid.uuid4()) if not experiment_name else experiment_name
    packages = [p._key + '==' + p._version for p in
                pip.pip.get_installed_distributions(local_only=True)]

    return Experiment(
        key=key,
        filename=filename,
        args=args,
        pythonenv=packages,
        project=project)


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, database_config):
        guest = database_config['guest'] if 'guest' in \
            database_config.keys() else False

        app = pyrebase.initialize_app(database_config)
        self.db = app.database()
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(10)
        self.storage = app.storage()

        self.auth = FirebaseAuth(app) if not guest else None

        if self.auth:
            self.__setitem__(self._get_user_keybase() + "email",
                             self.auth.get_user_email())

    def __getitem__(self, key):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.db.child(key_path).child(key_name)
            return dbobj.get(self.auth.get_token()).val() if self.auth \
                else dbobj.get().val()
        except Exception as err:
            self.logger.error("Getting key {} from a database \
                               raised an exception: {}".format(key, err))
            return None

    def __setitem__(self, key, value):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.db.child(key_path)
            if self.auth:
                dbobj.update({key_name: value}, self.auth.get_token())
            else:
                dbobj.update({key_name: value})
        except Exception as err:
            self.logger.error("Putting key {}, value {} into a database \
                               raised an exception: {}"
                              .format(key, value, err))

    def _upload_file(self, key, local_file_path):
        try:
            storageobj = self.storage.child(key)
            if self.auth:
                storageobj.put(local_file_path, self.auth.get_token())
            else:
                storageobj.put(local_file_path)
        except Exception as err:
            self.logger.error("Uploading file {} with key {} into storage \
                               raised an exception: {}"
                              .format(local_file_path, key, err))

    def _download_file(self, key, local_file_path):
        try:
            storageobj = self.storage.child(key)

            if self.auth:
                storageobj.download(local_file_path, self.auth.get_token())
            else:
                storageobj.download(local_file_path)
        except Exception as err:
            self.logger.error("Downloading file {} to local path {} from storage \
                               raised an exception: {}"
                              .format(key, local_file_path, err))

    def _upload_dir(self, key, local_path):
        if os.path.exists(local_path):
            tar_filename = os.path.join(tempfile.gettempdir(),
                                        str(uuid.uuid4()))
            self.logger.debug('Tarring and uploading directrory. \
                              tar_filename = %s, \
                              local_path = %s, \
                              key = %s' % (tar_filename, local_path, key))

            subprocess.call([
                '/bin/bash',
                '-c',
                'cd %s && tar -czf %s . ' % (local_path, tar_filename)])

            self._upload_file(key, tar_filename)
            os.remove(tar_filename)
        else:
            self.logger.debug('Local path %s does not exist. \
                               Not uploading anything.' % (local_path))

    def _download_dir(self, key, local_path):
        tar_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        self._download_file(key, tar_filename)
        if os.path.exists(tar_filename):
            subprocess.call([
                '/bin/bash',
                '-c',
                'mkdir -p %s && \
                tar -xzf %s -C %s --keep-newer-files'
                % (local_path, tar_filename, local_path)])

            os.remove(tar_filename)

    def _delete(self, key):
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
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def add_experiment(self, experiment):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'
        self.__setitem__(self._get_experiments_keybase() + experiment.key,
                         experiment.__dict__)
        Thread(target=self._upload_dir,
               args=(self._get_experiments_keybase() +
                     experiment.key + "/workspace.tgz",
                     experiment.workspace_path)
               ).start()

        self.__setitem__(self._get_user_keybase() + "experiments/" +
                         experiment.key,
                         experiment.key)

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() +
                             experiment.project + "/" +
                             experiment.key + "/userId",
                             self.auth.get_user_id())

    def start_experiment(self, experiment):
        experiment.time_started = time.time()
        experiment.status = 'running'
        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/status",
                         "running")

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_started",
                         experiment.time_started)

        self.checkpoint_experiment(experiment)

    def finish_experiment(self, experiment):
        self.checkpoint_experiment(experiment)
        experiment.status = 'finished'
        experiment.time_finished = time.time()
        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/status",
                         "finished")

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_finished",
                         experiment.time_finished)

    def checkpoint_experiment(self, experiment, blocking=False):
        checkpoint_threads = [
            Thread(
                target=self._upload_dir,
                args=(self._get_experiments_keybase() +
                      experiment.key + "/workspace_latest.tgz",
                      experiment.workspace_path)
            ),

            Thread(
                target=self._upload_dir,
                args=(self._get_experiments_keybase() +
                      experiment.key + "/modeldir.tgz",
                      experiment.model_dir)
            )
        ]

        for t in checkpoint_threads:
            t.start()
        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_last_checkpoint",
                         time.time())
        return checkpoint_threads

    def _experiment(self, key, data, info={}):
        return Experiment(
            key=key,
            filename=data['filename'],
            args=data['args'] if 'args' in data.keys() else None,
            pythonenv=data['pythonenv'],
            project=data['project'] if 'project' in data.keys() else None,
            status=data['status'],
            time_added=data['time_added'],
            time_started=data['time_started']
            if 'time_started' in data.keys() else None,
            time_last_checkpoint=data['time_last_checkpoint']
            if 'time_last_checkpoint' in data.keys() else None,
            time_finished=data['time_finished']
            if 'time_finished' in data.keys() else None,
            info=info
        )

    def _download_modeldir(self, key):
        self.logger.info("Downloading model directory...")
        self._download_dir(self._get_experiments_keybase() +
                           key + '/modeldir.tgz',
                           fs_tracker.get_model_directory(key))
        self.logger.info("Done")

    def _get_experiment_info(self, key):
        self._download_modeldir(key)
        local_modeldir = fs_tracker.get_model_directory(key)
        info = {}
        hdf5_files = glob.glob(os.path.join(local_modeldir, '*.hdf'))
        type_found = False
        if any(hdf5_files):
            info['type'] = 'keras'
            info['no_checkpoints'] = len(hdf5_files)
            type_found = True

        meta_files = glob.glob(os.path.join(local_modeldir, '*.meta'))
        if any(meta_files) and not type_found:
            info['type'] = 'tensorflow'
            global_step = checkpoint_utils.load_variable(
                local_modeldir, 'global_step')

            info['global_step'] = global_step
            type_found = True

        if not type_found:
            info['type'] = 'unknown'

        logpath = os.path.join(
            fs_tracker.get_model_directory(key), 'output.log')

        if os.path.exists(logpath):
            tailp = subprocess.Popen(
                ['tail', '-50', logpath], stdout=subprocess.PIPE)
            logtail = [_remove_backspaces(line) for line in tailp.stdout]
            info['logtail'] = logtail

        return info

    def get_experiment(self, key, getinfo=True):
        data = self.__getitem__(self._get_experiments_keybase() + key)
        info = self._get_experiment_info(key) if getinfo else {}
        assert data, "data at path %s not found! " % (
            self._get_experiments_keybase() + key)
        return self._experiment(key, data, info)

    def get_user_experiments(self, userid=None):
        experiment_keys = self.__getitem__(
            self._get_user_keybase(userid) + "/experiments")
        if not experiment_keys:
            experiment_keys = {}

        experiments = []
        for key in experiment_keys.keys() if experiment_keys else []:
            experiments.append(self.get_experiment(key, getinfo=False))
        return experiments

    def get_projects(self):
        return self.__getitem__(self._get_projects_keybase())

    def get_users(self):
        return self.__getitem__('users/')


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


def _remove_backspaces(line):
    while '\x08' in line:
        line = re.sub('[^\x08]\x08', '', line)
    return line
