"""Data providers."""

import os
import pip
import uuid

import yaml
import pyrebase
import logging
import time
import glob
from threading import Thread
import subprocess

from tensorflow.contrib.framework.python.framework import checkpoint_utils

import fs_tracker
import util
import git_util
from auth import FirebaseAuth
from artifact_store import FirebaseArtifactStore
from model_util import KerasModelWrapper


logging.basicConfig()


class Experiment(object):
    """Experiment information."""

    def __init__(self, key, filename, args, pythonenv,
                 project=None,
                 artifacts=None,
                 status='waiting',
                 resources_needed=None,
                 time_added=None,
                 time_started=None,
                 time_last_checkpoint=None,
                 time_finished=None,
                 info={},
                 git=None):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project
        workspace_path = '.'
        model_dir = fs_tracker.get_model_directory(key)

        self.artifacts = {
            'workspace': {
                'local': workspace_path,
                'mutable': True
            },
            'modeldir': {
                'local': model_dir,
                'mutable': True
            },
            'output': {
                'local': fs_tracker.get_artifact_cache('output', key),
                'mutable': True
            },
            'tb': {
                'local': fs_tracker.get_tensorboard_dir(key),
                'mutable': True
            }
        }
        if artifacts is not None:
            self.artifacts.update(artifacts)

        self.resources_needed = resources_needed
        self.status = status
        self.time_added = time_added
        self.time_started = time_started
        self.time_last_checkpoint = time_last_checkpoint
        self.time_finished = time_finished
        self.info = info
        self.git = git

    def get_model(self):
        if self.info.get('type') == 'keras':
            hdf5_files = [
                (p, os.path.getmtime(p))
                for p in
                glob.glob(self.artifacts['modeldir'] + '/*.hdf*') +
                glob.glob(self.artifacts['modeldir'] + '/*.h5')]

            last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
            return KerasModelWrapper(last_checkpoint)

        if self.info.get('type') == 'tensorflow':
            raise NotImplementedError

        raise ValueError("Experiment type is unknown!")


def create_experiment(
        filename,
        args,
        experiment_name=None,
        project=None,
        artifacts={},
        resources_needed=None):
    key = str(uuid.uuid4()) if not experiment_name else experiment_name
    packages = [p._key + '==' + p._version for p in
                pip.pip.get_installed_distributions(local_only=True)]

    return Experiment(
        key=key,
        filename=filename,
        args=args,
        pythonenv=packages,
        project=project,
        artifacts=artifacts,
        resources_needed=resources_needed)


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, database_config, blocking_auth=True):
        guest = database_config.get('guest')

        self.app = pyrebase.initialize_app(database_config)
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(10)

        self.auth = FirebaseAuth(self.app,
                                 database_config.get("use_email_auth"),
                                 database_config.get("email"),
                                 database_config.get("password"),
                                 blocking_auth) \
            if not guest else None

        self.store = FirebaseArtifactStore(self.app, self.auth)
        self._experiment_info_cache = {}

        if self.auth and not self.auth.expired:
            self.__setitem__(self._get_user_keybase() + "email",
                             self.auth.get_user_email())

    def __getitem__(self, key):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.app.database().child(key_path).child(key_name)
            return dbobj.get(self.auth.get_token()).val() if self.auth \
                else dbobj.get().val()
        except Exception as err:
            self.logger.error(("Getting key {} from a database " +
                               "raised an exception: {}").format(key, err))
            return None

    def __setitem__(self, key, value):
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
            self.logger.error(("Putting key {}, value {} into a database " +
                               "raised an exception: {}")
                              .format(key, value, err))

    def _delete(self, key):
        dbobj = self.app.database().child(key)

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

        experiment.git = git_util.get_git_info(
            experiment.artifacts['workspace']['local'])

        for tag, art in experiment.artifacts.iteritems():
            if art['mutable']:
                art['key'] = self._get_experiments_keybase() + \
                    experiment.key + '/' + tag + '.tgz'
            else:
                if 'local' in art.keys():
                    # upload immutable artifacts
                    art['key'] = self.store.put_artifact(art)

        self.__setitem__(self._get_experiments_keybase() + experiment.key,
                         experiment.__dict__)

        self.__setitem__(self._get_user_keybase() + "experiments/" +
                         experiment.key,
                         experiment.key)

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() +
                             experiment.project + "/" +
                             experiment.key + "/userId",
                             self.auth.get_user_id())

        self.checkpoint_experiment(experiment, blocking=True)

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
        self.checkpoint_experiment(experiment, blocking=True)
        experiment.status = 'finished'
        experiment.time_finished = time.time()
        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/status",
                         "finished")

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_finished",
                         experiment.time_finished)

    def delete_experiment(self, experiment_key):
        experiment = self.get_experiment(experiment_key)
        self._delete(self._get_user_keybase() + 'experiments/' +
                     experiment_key)

        for tag, art in experiment.artifacts.iteritems():
            self.logger.debug('Deleting artifact {} from the store, ' +
                              'artifact key {}'.format(tag, art['key']))
            self.store.delete_artifact(art)

        self._delete(self._get_experiments_keybase() + experiment_key)

    def checkpoint_experiment(self, experiment, blocking=False):
        checkpoint_threads = [
            Thread(
                target=self.store.put_artifact,
                args=(art,))
            for _, art in experiment.artifacts.iteritems()
            if art['mutable']]

        for t in checkpoint_threads:
            t.start()
            t.join()

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_last_checkpoint",
                         time.time())
        if blocking:
            for t in checkpoint_threads:
                pass
                # t.join()
        else:
            return checkpoint_threads

    def _experiment(self, key, data, info={}):
        return Experiment(
            key=key,
            filename=data['filename'],
            args=data.get('args'),
            pythonenv=data['pythonenv'],
            project=data.get('project'),
            status=data['status'],
            artifacts=data.get('artifacts'),
            resources_needed=data.get('resources_needed'),
            time_added=data['time_added'],
            time_started=data.get('time_started'),
            time_last_checkpoint=data.get('time_last_checkpoint'),
            time_finished=data.get('time_finished'),
            info=info,
            git=data.get('git')
        )

    def _get_experiment_info(self, experiment):
        local_modeldir = self.store.get_artifact(
            experiment.artifacts['modeldir'])
        info = {}
        hdf5_files = glob.glob(os.path.join(local_modeldir, '*.hdf*'))
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

        info['logtail'] = self.get_experiment_logtail(experiment.key)

        return info

    def _get_experiment_logtail(self, experiment):
        logpath = self.store.get_artifact(experiment.artifacts['output'])

        if os.path.exists(logpath):
            tailp = subprocess.Popen(
                ['tail', '-50', logpath], stdout=subprocess.PIPE)
            stdoutdata = tailp.communicate()[0]
            logtail = util.remove_backspaces(stdoutdata).split('\n')

            return logtail
        else:
            return None

    def get_experiment(self, key, getinfo=True):
        data = self.__getitem__(self._get_experiments_keybase() + key)
        assert data, "data at path %s not found! " % (
            self._get_experiments_keybase() + key)

        experiment_stub = self._experiment(key, data, {})

        if getinfo:
            self._start_info_download(experiment_stub)

        info = self._experiment_info_cache.get(key)

        return self._experiment(key, data, info)

    def _start_info_download(self, experiment):
        key = experiment.key
        if key not in self._experiment_info_cache.keys():
            self._experiment_info_cache[key] = {}

        self._experiment_info_cache[key]['logtail'] = \
            self._get_experiment_logtail(experiment)

        def download_info():
            self._experiment_info_cache[key].update(
                self._get_experiment_info(experiment)
            )
        if not (experiment.status == 'finished' and
                any(self._experiment_info_cache[key])):
            Thread(target=download_info)

    def get_user_experiments(self, userid=None):
        experiment_keys = self.__getitem__(
            self._get_user_keybase(userid) + "/experiments")
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(experiment_keys.keys())

    def get_project_experiments(self, project):
        experiment_keys = self.__getitem__(self._get_projects_keybase()
                                           + project)
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(experiment_keys.keys())

    def get_artifacts(self, key):
        experiment = self.get_experiment(key, getinfo=False)
        retval = {}
        if experiment.artifacts is not None:
            for tag, art in experiment.artifacts.iteritems():
                url = self.store.get_artifact_url(art)
                if url is not None:
                    retval[tag] = url

        return retval

    def _get_valid_experiments(self, experiment_keys):
        experiments = []
        for key in experiment_keys:
            try:
                experiment = self.get_experiment(key, getinfo=False)
                experiments.append(experiment)
            except AssertionError:
                self.logger.warn(
                    ("Experiment {} does not exist " +
                     "or is corrupted, deleting record").format(key))
                try:
                    self.delete_experiment(key)
                except BaseException:
                    pass
        return experiments

    def get_projects(self):
        return self.__getitem__(self._get_projects_keybase())

    def get_users(self):
        return self.__getitem__('users/')

    def refresh_auth_token(self, email, refresh_token):
        if self.auth:
            self.auth.refresh_token(email, refresh_token)

    def get_auth_domain(self):
        return self.app.auth_domain

    def is_auth_expired(self):
        if self.auth:
            return self.auth.expired
        else:
            return False


class PostgresProvider(object):
    """Data provider for Postgres."""

    def __init__(self, connection_uri):
        # TODO: implement connection
        pass

    def add_experiment(self, experiment):
        raise NotImplementedError()

    def delete_experiment(self, experiment):
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

    def get_project_experiments(self):
        raise NotImplementedError()

    def get_artifacts(self):
        raise NotImplementedError()

    def get_users(self):
        raise NotImplementedError()

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()

    def refresh_auth_token(self, email, refresh_token):
        raise NotImplementedError()

    def get_auth_domain(self):
        raise NotImplementedError()

    def is_auth_expired(self):
        raise NotImplementedError()


def get_config(config_file=None):
    def_config_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "default_config.yaml")
    with open(def_config_file) as f:
        config = yaml.load(f.read())

    if config_file:
        with open(config_file) as f:
            config.update(yaml.load(f.read()))

    return config


def get_db_provider(config=None, blocking_auth=True):
    if not config:
        config = get_config()
    assert 'database' in config.keys()
    db_config = config['database']
    assert db_config['type'].lower() == 'firebase'.lower()

    if 'projectId' in db_config.keys():
        projectId = db_config['projectId']
        db_config['authDomain'] = db_config['authDomain'].format(projectId)
        db_config['databaseURL'] = db_config['databaseURL'].format(projectId)
        db_config['storageBucket'] = db_config['storageBucket'].format(
            projectId)

    return FirebaseProvider(db_config, blocking_auth)
