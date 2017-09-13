"""Data providers."""

import os
import uuid

try:
    # try-except statement needed because
    # pip module is not available in google app engine
    import pip
except ImportError:
    pip = None

import yaml
import pyrebase
import logging
import time
import glob
from threading import Thread
try:
    from multiprocessing.pool import ThreadPool
except ImportError:
    ThreadPool = None

import fs_tracker
import util
import git_util
from auth import FirebaseAuth
from artifact_store import get_artifact_store
from firebase_artifact_store import FirebaseArtifactStore

from http_provider import HTTPProvider

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
            import keras
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


def experiment_from_dict(data, info={}):
    return Experiment(
        key=data['key'],
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


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, db_config, blocking_auth=True, verbose=10, store=None):
        guest = db_config.get('guest')

        self.app = pyrebase.initialize_app(db_config)
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(verbose)

        self.auth = None
        if not guest and 'serviceAccount' not in db_config.keys():
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

        if ThreadPool:
            self.pool = ThreadPool(iothreads)
        else:
            self.pool = None

        if self.auth and not self.auth.expired:
            self.__setitem__(self._get_user_keybase() + "email",
                             self.auth.get_user_email())

        self.max_keys = db_config.get('max_keys', 100)

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

    def _delete(self, key, token=None):
        dbobj = self.app.database().child(key)

        if self.auth:
            dbobj.remove(self.auth.get_token())
        else:
            dbobj.remove()

    def _get_userid(self):
        userid = None
        if self.auth:
            userid = self.auth.get_user_id()
        userid = userid if userid else 'guest'
        return userid

    def _get_user_keybase(self, userid=None):
        if userid is None:
            userid = self._get_userid()

        return "users/" + userid + "/"

    def _get_experiments_keybase(self, userid=None):
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def add_experiment(self, experiment, userid=None):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'

        if 'local' in experiment.artifacts['workspace'].keys() and \
                os.path.exists(experiment.artifacts['workspace']['local']):
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

        userid = userid if userid else self._get_userid()

        experiment_dict = experiment.__dict__.copy()
        experiment_dict['owner'] = userid

        self.__setitem__(self._get_experiments_keybase() + experiment.key,
                         experiment_dict)

        self.__setitem__(self._get_user_keybase(userid) + "experiments/" +
                         experiment.key,
                         experiment.time_added)

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() +
                             experiment.project + "/" +
                             experiment.key + "/owner",
                             userid)

        self.checkpoint_experiment(experiment, blocking=True)
        self.logger.info("Added experiment " + experiment.key)

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
        time_finished = time.time()
        if isinstance(experiment, basestring):
            key = experiment
        else:
            key = experiment.key
            self.checkpoint_experiment(experiment, blocking=True)
            experiment.status = 'finished'
            experiment.time_finished = time_finished

        self.__setitem__(self._get_experiments_keybase() +
                         key + "/status",
                         "finished")

        self.__setitem__(self._get_experiments_keybase() +
                         key + "/time_finished",
                         time_finished)

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
        if isinstance(experiment, basestring):
            key = experiment
            experiment = self.get_experiment(key, getinfo=False)
        else:
            key = experiment.key

        checkpoint_threads = [
            Thread(
                target=self.store.put_artifact,
                args=(art,))
            for _, art in experiment.artifacts.iteritems()
            if art['mutable'] and art.get('local')]

        for t in checkpoint_threads:
            t.start()

        self.__setitem__(self._get_experiments_keybase() +
                         key + "/time_last_checkpoint",
                         time.time())
        if blocking:
            for t in checkpoint_threads:
                t.join()
        else:
            return checkpoint_threads

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

        if experiment.metric is not None:
            metric_str = experiment.metric.split(':')
            metric_name = metric_str[0]
            metric_type = metric_str[1] if len(metric_str) > 1 else None

            tbtar = self.store.stream_artifact(experiment.artifacts['tb'])

            if metric_type == 'min':
                def metric_accum(x, y): return min(x, y) if x else y
            elif metric_type == 'max':
                def metric_accum(x, y): return max(x, y) if x else y
            else:
                def metric_accum(x, y): return y

            metric_value = None
            for f in tbtar:
                if f.isreg():
                    for e in util.event_reader(tbtar.extractfile(f)):
                        for v in e.summary.value:
                            if v.tag == metric_name:
                                metric_value = metric_accum(
                                    metric_value, v.simple_value)

            info['metric_value'] = metric_value

        return info

    def _get_experiment_logtail(self, experiment):
        try:
            tarf = self.store.stream_artifact(experiment.artifacts['output'])
            if not tarf:
                return None

            logdata = tarf.extractfile(tarf.members[0]).read()
            logdata = util.remove_backspaces(logdata).split('\n')
            return logdata
        except BaseException as e:
            self.logger.info('Getting experiment logtail raised an exception:')
            self.logger.info(e)
            return None

    def get_experiment(self, key, getinfo=True):
        data = self.__getitem__(self._get_experiments_keybase() + key)
        assert data, "data at path %s not found! " % (
            self._get_experiments_keybase() + key)
        data['key'] = key

        experiment_stub = experiment_from_dict(data)

        if getinfo:
            self._start_info_download(experiment_stub)

        info = self._experiment_info_cache.get(key)[0] \
            if self._experiment_info_cache.get(key) else None

        return experiment_from_dict(data, info)

    def _start_info_download(self, experiment):
        key = experiment.key
        if key not in self._experiment_info_cache.keys():
            self._experiment_info_cache[key] = ({}, time.time())

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
                Thread(target=download_info).start()
            else:
                download_info()

    def get_user_experiments(self, userid=None, blocking=True):
        if userid and '@' in userid:
            users = self.get_users()
            user_ids = [u for u in users if users[u].get('email') == userid]
            if len(user_ids) < 1:
                return None
            else:
                userid = user_ids[0]

        experiment_keys = self.__getitem__(
            self._get_user_keybase(userid) + "/experiments")
        if not experiment_keys:
            experiment_keys = {}

        keys = sorted(experiment_keys.keys(),
                      key=lambda k: experiment_keys[k],
                      reverse=True)

        return self._get_valid_experiments(
            keys, getinfo=True, blocking=blocking)

    def get_project_experiments(self, project):
        experiment_keys = self.__getitem__(self._get_projects_keybase() +
                                           project)
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

    def get_artifact(self, artifact, only_newer=True):
        return self.store.get_artifact(artifact, only_newer=only_newer)

    def _get_valid_experiments(self, experiment_keys,
                               getinfo=False, blocking=True):

        if self.max_keys > 0:
            experiment_keys = experiment_keys[:self.max_keys]

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

    def is_auth_expired(self):
        if self.auth:
            return self.auth.expired
        else:
            return False

    def can_write_experiment(self, key=None, user=None):
        assert key is not None
        user = user if user else self._get_userid()

        owner = self.__getitem__(
            self._get_experiments_keybase() + key + "/owner")
        if owner is None:
            return True
        else:
            return (owner == user)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.pool:
            self.pool.close()
        if self.app:
            self.app.requests.close()


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

    def get_artifact(self):
        raise NotImplementedError()

    def get_users(self):
        raise NotImplementedError()

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()

    def refresh_auth_token(self, email, refresh_token):
        raise NotImplementedError()

    def is_auth_expired(self):
        raise NotImplementedError()

    def can_write_experiment(self, key=None, user=None):
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
                    if isinstance(value, basestring):
                        config[key] = os.path.expandvars(value)

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

    logger = logging.getLogger("get_db_provider")
    logger.setLevel(verbose)
    logger.debug('Choosing db provider with config:')
    logger.debug(config)

    if 'storage' in config.keys():
        artifact_store = get_artifact_store(
            config['storage'],
            blocking_auth=blocking_auth,
            verbose=verbose)
    else:
        artifact_store = None

    assert 'database' in config.keys()
    db_config = config['database']
    if db_config['type'].lower() == 'firebase':
        return FirebaseProvider(
            db_config,
            blocking_auth,
            verbose=verbose,
            store=artifact_store)
    elif db_config['type'].lower() == 'http':
        return HTTPProvider(db_config)
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
