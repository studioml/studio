import os
import glob
import uuid
import sys

try:
    import pip
except ImportError:
    pip = None

from . import fs_tracker


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
                 metric=None,
                 pythonver=None,
                 max_duration=None):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project
        self.pythonver = pythonver if pythonver else sys.version_info[0]

        workspace_path = os.path.abspath('.')
        try:
            model_dir = fs_tracker.get_model_directory(key)
        except BaseException:
            model_dir = None

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
            },
            '_metrics': {
                'local': fs_tracker.get_artifact_cache('_metrics', key),
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
        self.max_duration = max_duration

    def get_model(self, db):
        modeldir = db.get_artifact(self.artifacts['modeldir'])
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
        metric=None,
        max_duration=None):
    key = str(uuid.uuid4()) if not experiment_name else experiment_name
    packages = set([])
    for i, pkg in enumerate(
            pip.pip.get_installed_distributions(local_only=True)):
        if resources_needed is not None and \
           int(resources_needed.get('gpus')) > 0:
            if pkg.key == 'tensorflow':
                pkg._key = 'tensorflow-gpu'
            if pkg.key == 'tf-nightly':
                pkg._key = 'tf-nightly-gpu'
        else:
            if pkg.key == 'tensorflow-gpu':
                pkg._key = 'tensorflow'
            if pkg.key == 'tf-nightly-gpu':
                pkg._key = 'tf-nightly'

        packages.add(pkg._key + '==' + pkg._version)

    return Experiment(
        key=key,
        filename=filename,
        args=args,
        pythonenv=[p for p in packages],
        project=project,
        artifacts=artifacts,
        resources_needed=resources_needed,
        metric=metric,
        max_duration=max_duration)


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
        info=info if any(info) else data.get('info'),
        git=data.get('git'),
        metric=data.get('metric'),
        pythonver=data.get('pythonver'),
        max_duration=data.get('max_duration')
    )
