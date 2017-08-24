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
from multiprocessing.pool import ThreadPool
import subprocess

import tensorflow as tf
try:
    import keras
except BaseException:
    keras = None

import fs_tracker
import util
import git_util
from auth import FirebaseAuth
from artifact_store import get_artifact_store
from firebase_artifact_store import FirebaseArtifactStore


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
                 git=None,
                 metric=None):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project

        workspace_path = os.path.abspath('.')
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
        self.metric = metric

    def get_model(self, db):
        modeldir = db.store.get_artifact(self.artifacts['modeldir'])
        hdf5_files = [
            (p, os.path.getmtime(p))
            for p in
            glob.glob(modeldir + '/*.hdf*') +
            glob.glob(modeldir + '/*.h5')]
        if any(hdf5_files):
            # experiment type - keras
            assert keras is not None
            last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
            return keras.models.load_model(last_checkpoint)

        if self.info.get('type') == 'tensorflow':
            raise NotImplementedError

        raise ValueError("Experiment type is unknown!")


def create_experiment(
        filename,
        args,
        experiment_name=None,
        project=None,
        artifacts={},
        resources_needed=None,
        metric=None):
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
        resources_needed=resources_needed,
        metric=metric)


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, db_config, blocking_auth=True, verbose=10, store=None):
        guest = db_config.get('guest')

        self.app = pyrebase.initialize_app(db_config)
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(verbose)

        if guest or 'serviceAccount' in db_config.keys():
            self.auth = None
        else:
            self.auth = FirebaseAuth(self.app,
                                     db_config.get("use_email_auth"),
                                     db_config.get("email"),
                                     db_config.get("password"),
                                     blocking_auth)

        self.store = store if store else FirebaseArtifactStore(
            db_config, verbose=verbose, blocking_auth=blocking_auth)

        self._experiment_info_cache = {}
        self._experiment_cache = {}

        iothreads = 10
        self.pool = ThreadPool(iothreads)

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
            self.logger.warn(("Getting key {} from a database " +
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
            self.logger.warn(("Putting key {}, value {} into a database " +
                              "raised an exception: {}")
                             .format(key, value, err))

    def _delete(self, key):
        dbobj = self.app.database().child(key)

        if self.auth:
            dbobj.remove(self.auth.get_token())
        else:
            dbobj.remove()

    def _get_userid(self):
        if not self.auth:
            userid = 'guest'
        else:
            userid = self.auth.get_user_id()
        return userid

    def _get_user_keybase(self, userid=None):
        if userid is None:
            userid = self._get_userid()

        return "users/" + userid + "/"

    def _get_experiments_keybase(self, userid=None):
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def add_experiment(self, experiment):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'

        if os.path.exists(experiment.artifacts['workspace']['local']):
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

            if 'key' in art.keys():
                art['qualified'] = self.store.get_qualified_location(
                    art['key'])

            art['bucket'] = self.store.get_bucket()

        experiment_dict = experiment.__dict__.copy()
        experiment_dict['owner'] = self._get_userid()

        self.__setitem__(self._get_experiments_keybase() + experiment.key,
                         experiment_dict)

        self.__setitem__(self._get_user_keybase() + "experiments/" +
                         experiment.key,
                         experiment.key)

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() +
                             experiment.project + "/" +
                             experiment.key + "/owner",
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

    def stop_experiment(self, key):
        # can be called remotely (the assumption is
        # that remote worker checks experiments status periodically,
        # and if it is 'stopped', kills the experiment.
        if isinstance(key, Experiment):
            key = key.key

        self.__setitem__(self._get_experiments_keybase() +
                         key + "/status",
                         "stopped")

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

    def delete_experiment(self, experiment):
        if isinstance(experiment, basestring):
            experiment_key = experiment
            try:
                experiment = self.get_experiment(experiment)
                experiment_key = experiment.key
            except BaseException:
                experiment = None
        else:
            experiment_key = experiment.key

        self._delete(self._get_user_keybase() + 'experiments/' +
                     experiment_key)

        if experiment_key in self._experiment_cache.keys():
            del self._experiment_cache[experiment_key]
        if experiment_key in self._experiment_info_cache.keys():
            del self._experiment_info_cache[experiment_key]

        if experiment is not None:
            for tag, art in experiment.artifacts.iteritems():
                if art.get('key') is not None:
                    self.logger.debug(
                        ('Deleting artifact {} from the store, ' +
                         'artifact key {}').format(tag, art['key']))
                    self.store.delete_artifact(art)

        if experiment.project is not None:
            self._delete(
                self._get_projects_keybase() +
                experiment.project +
                "/" +
                experiment.key)

        self._delete(self._get_experiments_keybase() + experiment.key)

    def checkpoint_experiment(self, experiment, blocking=False):
        checkpoint_threads = [
            Thread(
                target=self.store.put_artifact,
                args=(art,))
            for _, art in experiment.artifacts.iteritems()
            if art['mutable']]

        for t in checkpoint_threads:
            t.start()

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_last_checkpoint",
                         time.time())
        if blocking:
            for t in checkpoint_threads:
                t.join()
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
            git=data.get('git'),
            metric=data.get('metric')
        )

    def _get_experiment_info(self, experiment):
        info = {}
        type_found = False
        '''
        local_modeldir = self.store.get_artifact(
            experiment.artifacts['modeldir'])
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
        '''

        if not type_found:
            info['type'] = 'unknown'

        info['logtail'] = self._get_experiment_logtail(experiment)

        tbpath = self.store.get_artifact(experiment.artifacts['tb'])
        eventfiles = glob.glob(os.path.join(tbpath, "*"))

        if experiment.metric is not None:
            metric_str = experiment.metric.split(':')
            metric_name = metric_str[0]
            metric_type = metric_str[1] if len(metric_str) > 1 else None

            if metric_type == 'min':
                def metric_accum(x, y): return min(x, y) if x else y
            elif metric_type == 'max':
                def metric_accum(x, y): return max(x, y) if x else y
            else:
                def metric_accum(x, y): return y

            metric_value = None
            for f in eventfiles:
                for e in tf.train.summary_iterator(f):
                    for v in e.summary.value:
                        if v.tag == metric_name:
                            metric_value = metric_accum(
                                metric_value, v.simple_value)

            info['metric_value'] = metric_value

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

        info = self._experiment_info_cache.get(key)[0] \
            if self._experiment_info_cache.get(key) else None

        return self._experiment(key, data, info)

    def _start_info_download(self, experiment):
        key = experiment.key
        if key not in self._experiment_info_cache.keys():
            self._experiment_info_cache[key] = ({}, time.time())

        try:
            pass
            # self._experiment_info_cache[key]['logtail'] = \
            #    self._get_experiment_logtail(experiment)

            # self._experiment_info_cache[key] = \
            #     self._get_experiment_info(experiment)
        except Exception:
            pass

        def download_info():
            try:
                self._experiment_info_cache[key] = (
                    self._get_experiment_info(experiment),
                    time.time())

                self.logger.debug("Finished info download for " + key)
            except Exception as e:
                self.logger.info(
                    "Exception {} while info download for {}".format(
                        e, key))

        if not(any(self._experiment_info_cache[key][0])) or \
           self._experiment_info_cache[key][1] < \
           experiment.time_last_checkpoint:

            self.logger.debug("Starting info download for " + key)
            if self.pool:
                self.pool.map_async(download_info, [None])
            else:
                download_info()

    def get_user_experiments(self, userid=None, blocking=True):
        experiment_keys = self.__getitem__(
            self._get_user_keybase(userid) + "/experiments")
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(
            experiment_keys.keys(), getinfo=True, blocking=blocking)

    def get_project_experiments(self, project):
        experiment_keys = self.__getitem__(self._get_projects_keybase()
                                           + project)
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(
            experiment_keys.keys(), getinfo=True)

    def get_artifacts(self, key):
        experiment = self.get_experiment(key, getinfo=False)
        retval = {}
        if experiment.artifacts is not None:
            for tag, art in experiment.artifacts.iteritems():
                url = self.store.get_artifact_url(art)
                if url is not None:
                    retval[tag] = url

        return retval

    def _get_valid_experiments(self, experiment_keys,
                               getinfo=False, blocking=True):
        def cache_valid_experiment(key):
            try:
                self._experiment_cache[key] = self.get_experiment(
                    key, getinfo=getinfo)
            except AssertionError:
                self.logger.warn(
                    ("Experiment {} does not exist " +
                     "or is corrupted, try to delete record").format(key))
                try:
                    self.delete_experiment(key)
                except BaseException:
                    pass

        if self.pool:
            if blocking:
                self.pool.map(cache_valid_experiment, experiment_keys)
            else:
                self.pool.map_async(cache_valid_experiment, experiment_keys)
        else:
            for e in experiment_keys:
                cache_valid_experiment(e)

        return [self._experiment_cache[key] for key in experiment_keys
                if key in self._experiment_cache.keys()]

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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.pool:
            self.pool.close()


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

    def stop_experiment(self, experiment):
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

    config_paths = []
    if config_file:
        config_paths.append(os.path.expanduser(config_file))

    config_paths.append(os.path.expanduser('~/.studioml/config.yaml'))
    config_paths.append(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "default_config.yaml"))

    for path in config_paths:
        if not os.path.exists(path):
            continue

        with(open(path)) as f:
            config = yaml.load(f.read())

            def replace_with_env(config):
                for key, value in config.iteritems():
                    if isinstance(value, str) and value.startswith('$'):
                        config[key] = os.environ.get(value[1:])
                    elif isinstance(value, dict):
                        replace_with_env(value)

            replace_with_env(config)
            return config

    raise ValueError('None of the config paths {} exits!'
                     .format(config_paths))


def get_db_provider(config=None, blocking_auth=True):
    if not config:
        config = get_config()
    verbose = parse_verbosity(config.get('verbose'))

    if 'storage' in config.keys():
        artifact_store = get_artifact_store(
            config['storage'],
            blocking_auth=blocking_auth,
            verbose=verbose)
    else:
        artifact_store = None

    assert 'database' in config.keys()
    db_config = config['database']
    if db_config['type'].lower() == 'firebase'.lower():
        return FirebaseProvider(
            db_config,
            blocking_auth,
            verbose=verbose,
            store=artifact_store)
    else:
        raise ValueError('Unknown type of the database ' + db_config['type'])


def parse_verbosity(verbosity=None):
    if verbosity is None:
        return parse_verbosity('info')

    if verbosity == 'True':
        return parse_verbosity('info')

    logger_levels = {
        'debug': 10,
        'info': 20,
        'warn': 30,
        'error': 40,
        'crit': 50
    }

    if isinstance(verbosity, basestring):
        return logger_levels[verbosity]
    else:
        return int(verbosity)
