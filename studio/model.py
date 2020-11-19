"""Data providers."""
import os
import re
import yaml
import six
import uuid

from .firebase_provider import FirebaseProvider
from .http_provider import HTTPProvider
from .local_db_provider import LocalDbProvider
from .s3_provider import S3Provider
from .local_queue import LocalQueue
from .pubsub_queue import PubsubQueue
from .sqs_queue import SQSQueue
from .local_storage_handler import LocalStorageHandler
from .s3_storage_handler import S3StorageHandler
from .tartifact_store import TartifactStore
from .gcloud_worker import GCloudWorkerManager
from .ec2cloud_worker import EC2WorkerManager
from .qclient_cache import get_cached_queue, shutdown_cached_queue
from .util import parse_verbosity
from .auth import get_auth

from .model_setup import setup_model, get_model_db_provider,\
    reset_model, set_model_verbose_level
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
            config = yaml.load(f.read(), Loader=yaml.FullLoader)

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

def reset_model_providers():
    reset_model()

def get_artifact_store(config):
    storage_type: str = config['type'].lower()

    if storage_type == 's3':
        return TartifactStore(S3StorageHandler(config))
    elif storage_type == 'local':
        return TartifactStore(LocalStorageHandler(config))
    else:
        raise ValueError('Unknown storage type: ' + storage_type)

def get_db_provider(config=None, blocking_auth=True):

    db_provider = get_model_db_provider()
    if db_provider is not None:
        return db_provider

    if config is None:
        config = get_config()
    verbose = parse_verbosity(config.get('verbose'))

    # Save this verbosity level as global for the whole experiment job:
    set_model_verbose_level(verbose)

    logger = logs.getLogger("get_db_provider")
    logger.setLevel(verbose)
    logger.debug('Choosing db provider with config:')
    logger.debug(config)

    if 'storage' in config.keys():
        artifact_store = get_artifact_store(config['storage'])
    else:
        artifact_store = None

    assert 'database' in config.keys()
    db_config = config['database']
    if db_config['type'].lower() == 'firebase':
        db_provider = FirebaseProvider(db_config,
                            blocking_auth=blocking_auth)

    elif db_config['type'].lower() == 'http':
        db_provider = HTTPProvider(db_config,
                            verbose=verbose,
                            blocking_auth=blocking_auth)

    elif db_config['type'].lower() == 's3':
        db_provider = S3Provider(db_config,
                          blocking_auth=blocking_auth)
        if artifact_store is None:
            artifact_store = db_provider.get_artifact_store()

    elif db_config['type'].lower() == 'gs':
        raise NotImplementedError("GS is not supported.")

    elif db_config['type'].lower() == 'local':
        db_provider = LocalDbProvider(db_config,
                          blocking_auth=blocking_auth)
        if artifact_store is None:
            artifact_store = db_provider.get_artifact_store()

    else:
        raise ValueError('Unknown type of the database ' + db_config['type'])

    setup_model(db_provider, artifact_store)
    return db_provider

def get_queue(
        queue_name=None,
        cloud=None,
        config=None,
        logger=None,
        close_after=None,
        verbose=10):
    if queue_name is None:
        if cloud in ['gcloud', 'gcspot']:
            queue_name = 'pubsub_' + str(uuid.uuid4())
        elif cloud in ['ec2', 'ec2spot']:
            queue_name = 'sqs_' + str(uuid.uuid4())
        else:
            queue_name = 'local'

    if queue_name.startswith('ec2') or \
       queue_name.startswith('sqs'):
        return SQSQueue(queue_name, verbose=verbose)
    elif queue_name.startswith('rmq_'):
        return get_cached_queue(
            name=queue_name,
            route='StudioML.' + queue_name,
            config=config,
            close_after=close_after,
            logger=logger,
            verbose=verbose)
    elif queue_name == 'local':
        return LocalQueue(verbose=verbose)
    else:
        return PubsubQueue(queue_name, verbose=verbose)

def shutdown_queue(queue, logger=None, delete_queue=True):
    if queue is None:
        return
    queue_name = queue.get_name()
    if queue_name.startswith("rmq_"):
        shutdown_cached_queue(queue, logger, delete_queue)
    else:
        queue.shutdown(delete_queue)

def get_worker_manager(config, cloud=None, verbose=10):
    if cloud is None:
        return None

    assert cloud in ['gcloud', 'gcspot', 'ec2', 'ec2spot']
    logger = logs.getLogger('runner.get_worker_manager')
    logger.setLevel(verbose)

    auth = get_auth(config['database']['authentication'])
    auth_cookie = auth.get_token_file() if auth else None

    branch = config['cloud'].get('branch')

    logger.info('using branch {}'.format(branch))

    if cloud in ['gcloud', 'gcspot']:

        cloudconfig = config['cloud']['gcloud']
        worker_manager = GCloudWorkerManager(
            auth_cookie=auth_cookie,
            zone=cloudconfig['zone'],
            branch=branch,
            user_startup_script=config['cloud'].get('user_startup_script')
        )

    if cloud in ['ec2', 'ec2spot']:
        worker_manager = EC2WorkerManager(
            auth_cookie=auth_cookie,
            branch=branch,
            user_startup_script=config['cloud'].get('user_startup_script')
        )
    return worker_manager

def add_packages(list1, list2):
    # This function dedups the package names which I think could be
    # functionally not desirable however rather than changing the behavior
    # instead we will do the dedup in a stable manner that prevents
    # package re-ordering
    pkgs = {re.sub('==.+', '', pkg): pkg for pkg in list1 + list2}
    merged = []
    for k in list1 + list2:
        v = pkgs.pop(re.sub('==.+', '', k), None)
        if v is not None:
            merged.append(v)
    return merged

