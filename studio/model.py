"""Data providers."""
import uuid

from studio.firebase_provider import FirebaseProvider
from studio.http_provider import HTTPProvider
from studio.pubsub_queue import PubsubQueue
from studio.gcloud_worker import GCloudWorkerManager
from studio.ec2cloud_worker import EC2WorkerManager
from studio.util.util import parse_verbosity
from studio.auth import get_auth

from studio.db_providers import db_provider_setup
from studio.queues import queues_setup
from studio.storage.storage_setup import setup_storage, get_storage_db_provider,\
    reset_storage, set_storage_verbose_level
from studio.util import logs

def reset_storage_providers():
    reset_storage()


def get_config(config_file=None):
    return db_provider_setup.get_config(config_file=config_file)


def get_db_provider(config=None, blocking_auth=True):

    db_provider = get_storage_db_provider()
    if db_provider is not None:
        return db_provider

    if config is None:
        config = get_config()
    verbose = parse_verbosity(config.get('verbose', None))

    # Save this verbosity level as global for the whole experiment job:
    set_storage_verbose_level(verbose)

    logger = logs.get_logger("get_db_provider")
    logger.setLevel(verbose)
    logger.debug('Choosing db provider with config:')
    logger.debug(config)

    if 'storage' in config.keys():
        artifact_store = db_provider_setup.get_artifact_store(config['storage'])
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
    else:
        db_provider = db_provider_setup.get_db_provider(
            config=config, blocking_auth=blocking_auth)

    setup_storage(db_provider, artifact_store)
    return db_provider

def get_queue(
        queue_name=None,
        cloud=None,
        config=None,
        logger=None,
        close_after=None,
        verbose=10):
    queue = queues_setup.get_queue(queue_name=queue_name,
                                   cloud=cloud,
                                   config=config,
                                   logger=logger,
                                   close_after=close_after,
                                   verbose=verbose)
    if queue is None:
        queue = PubsubQueue(queue_name, verbose=verbose)
    return queue

def shutdown_queue(queue, logger=None, delete_queue=True):
    queues_setup.shutdown_queue(queue, logger=logger, delete_queue=delete_queue)

def get_worker_manager(config, cloud=None, verbose=10):
    if cloud is None:
        return None

    assert cloud in ['gcloud', 'gcspot', 'ec2', 'ec2spot']
    logger = logs.get_logger('runner.get_worker_manager')
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

