"""Data providers."""
import os

try:
    # try-except statement needed because
    # pip module is not available in google app engine
    import pip
except ImportError:
    pip = None

import yaml
import six

from .artifact_store import get_artifact_store
from .http_provider import HTTPProvider
from .firebase_provider import FirebaseProvider
from .s3_provider import S3Provider
from .gs_provider import GSProvider
from . import logs


def get_config(config_file=None):

    config_paths = []
    if config_file:
        if not os.path.exists(config_file):
            raise ValueError('User config file {} not found'
                             .format(config_file))
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
                for key, value in six.iteritems(config):
                    if isinstance(value, six.string_types):
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

    logger = logs.getLogger("get_db_provider")
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
        return HTTPProvider(db_config,
                            verbose=verbose,
                            blocking_auth=blocking_auth)
    elif db_config['type'].lower() == 's3':
        return S3Provider(db_config,
                          verbose=verbose,
                          store=artifact_store,
                          blocking_auth=blocking_auth)

    elif db_config['type'].lower() == 'gs':
        return GSProvider(db_config,
                          verbose=verbose,
                          store=artifact_store,
                          blocking_auth=blocking_auth)

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

    if isinstance(verbosity, six.string_types) and \
       verbosity in logger_levels.keys():
        return logger_levels[verbosity]
    else:
        return int(verbosity)
