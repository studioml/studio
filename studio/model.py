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

import fs_tracker
import util
import git_util
from auth import FirebaseAuth
from artifact_store import get_artifact_store
from firebase_artifact_store import FirebaseArtifactStore

from http_provider import HTTPProvider
from firebase_provider import FirebaseProvider

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
        return HTTPProvider(db_config, blocking_auth=blocking_auth)
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
