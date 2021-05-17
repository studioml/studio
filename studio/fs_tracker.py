"""Utilities to track and record file system."""

import os
import shutil

from studio.artifacts import artifacts_tracker

STUDIOML_EXPERIMENT = 'STUDIOML_EXPERIMENT'
STUDIOML_HOME = 'STUDIOML_HOME'
STUDIOML_ARTIFACT_MAPPING = 'STUDIOML_ARTIFACT_MAPPING'


def get_experiment_key():
    return artifacts_tracker.get_experiment_key()


def get_studio_home():
    return artifacts_tracker.get_studio_home()


def setup_experiment(env, experiment, clean=True):
    artifacts_tracker.setup_experiment(env, experiment, clean=clean)


def get_artifact(tag):
    return artifacts_tracker.get_experiment(tag)


def get_artifacts():
    return artifacts_tracker.get_artifacts()


def get_model_directory(experiment_name=None):
    return get_artifact_cache('modeldir', experiment_name)


def get_artifact_cache(tag, experiment_name=None):
    return artifacts_tracker.get_artifact_cache(
        tag,
        experiment_name=experiment_name)


def get_blob_cache(blobkey):
    return artifacts_tracker.get_blob_cache(blobkey)

def get_model_directory(experiment_name=None):
    return get_artifact_cache('modeldir', experiment_name)

def _get_artifact_mapping_path(experiment_name=None):
    experiment_name = experiment_name if experiment_name else \
        os.environ[STUDIOML_EXPERIMENT]

    basepath = os.path.join(
        get_studio_home(),
        'artifact_mappings',
        experiment_name
    )
    if not os.path.exists(basepath):
        os.makedirs(basepath)

    return os.path.join(basepath, 'artifacts.json')


def _get_experiment_key(experiment):
    if not isinstance(experiment, str):
        return experiment.key
    else:
        return experiment


def _setup_model_directory(experiment_name, clean=False):
    path = get_model_directory(experiment_name)
    if clean and os.path.exists(path):
        shutil.rmtree(path)

    if not os.path.exists(path):
        os.makedirs(path)


def get_queue_directory():
    queue_dir = os.path.join(
        get_studio_home(),
        'queue')
    if not os.path.exists(queue_dir):
        try:
            os.makedirs(queue_dir)
        except OSError:
            pass

    return queue_dir


def get_tensorboard_dir(experiment_name=None):
    return get_artifact_cache('tb', experiment_name)
