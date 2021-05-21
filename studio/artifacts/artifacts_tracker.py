"""
    Utilities to track and record artifacts in local file system.
    Used both for client and evaluator execution.
"""

import os
import uuid
import json
import re
import shutil

from studio.util import util

STUDIOML_EXPERIMENT = 'STUDIOML_EXPERIMENT'
STUDIOML_HOME = 'STUDIOML_HOME'
STUDIOML_ARTIFACT_MAPPING = 'STUDIOML_ARTIFACT_MAPPING'


def get_experiment_key():
    if STUDIOML_EXPERIMENT not in os.environ.keys():
        key = str(uuid.uuid4())
        setup_experiment(os.environ, key)
    return os.environ[STUDIOML_EXPERIMENT]


def get_studio_home():
    if STUDIOML_HOME in os.environ.keys():
        return os.environ[STUDIOML_HOME]
    return os.path.join(os.path.expanduser('~'), '.studioml')

def _setup_model_directory(experiment_name, clean=False):
    path = get_artifact_cache('modeldir', experiment_name)
    if clean and os.path.exists(path):
        shutil.rmtree(path)

    if not os.path.exists(path):
        os.makedirs(path)

def setup_experiment(env, experiment, clean=True):
    if not isinstance(experiment, str):
        key = experiment.key
        artifacts = experiment.artifacts
    else:
        key = experiment
        artifacts = {}

    env[STUDIOML_EXPERIMENT] = key
    _setup_model_directory(key, clean)

    artifact_mapping_path = _get_artifact_mapping_path(key)
    env[STUDIOML_ARTIFACT_MAPPING] = artifact_mapping_path

    amapping = {}
    for tag, art in artifacts.items():
        # art is of type Artifact:
        if art.local_path is not None:
            amapping[tag] = art.local_path

        with open(artifact_mapping_path, 'w') as f_in:
            json.dump(amapping, f_in)


def get_artifact(tag):
    try:
        mapping_path = os.environ.get(STUDIOML_ARTIFACT_MAPPING)
        if mapping_path:
            with open(mapping_path, 'r') as f_in:
                a_mapping = json.load(f_in)
            return a_mapping[tag]
        return os.path.join(os.getcwd(), '..', tag)
    except BaseException:
        util.check_for_kb_interrupt()
        return None


def get_artifacts():
    try:
        mapping_path = os.environ.get(STUDIOML_ARTIFACT_MAPPING)
        if mapping_path:
            with open(mapping_path, 'r') as f_in:
                return json.load(f_in)
        else:
            artifacts = os.listdir(os.path.join(os.getcwd(), '..'))
            return {art: os.path.join(os.getcwd(), '..', art)
                    for art in artifacts}
    except BaseException:
        util.check_for_kb_interrupt()
        return {}


def get_artifact_cache(tag, experiment_name=None):
    assert tag is not None

    if tag.startswith('experiments/'):
        experiment_name = re.sub(
            r'\Aexperiments/',
            '',
            re.sub(
                r'/[^/]*\Z',
                '',
                tag))
        tag = re.sub(r'\.tar\.?[^\.]*\Z', '', re.sub('.*/', '', tag))

    if tag.startswith('blobstore/'):
        return get_blob_cache(tag)

    experiment_name = experiment_name if experiment_name else \
        get_experiment_key()
    retval = os.path.join(
        get_studio_home(),
        'experiments',
        experiment_name,
        tag
    )
    return retval


def get_blob_cache(blobkey):
    blobcache_dir = os.path.join(get_studio_home(), 'blobcache')
    if not os.path.exists(blobcache_dir):
        os.makedirs(blobcache_dir)

    blobkey = re.sub(r'\.tar\.?[^\.]*\Z', '', blobkey)
    if blobkey.startswith('blobstore/'):
        blobkey = re.sub('.*/', '', blobkey)

    return os.path.join(
        get_studio_home(),
        'blobcache',
        blobkey
    )


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


def get_tensorboard_dir(experiment_name=None):
    return get_artifact_cache('tb', experiment_name)
