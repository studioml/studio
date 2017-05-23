"""Utilities to track and record file system."""

import os

def get_model_directory(experiment_name=None):
    if experiment_name:
        return os.path.join(os.path.expanduser('~'), '.tfstudio/models/', experiment_name)
    else:
        return os.environ['TFSTUDIO_MODEL_PATH']


def setup_model_directory(env, experiment_name):
    path = get_model_directory(experiment_name)
    if not os.path.exists(path):
            os.makedirs(path)
    env['TFSTUDIO_MODEL_PATH'] = path
