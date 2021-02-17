import glob
import os
import uuid
import sys
import time

from . import fs_tracker
from .artifact import Artifact
from .util import shquote
from .dependencies_policy import DependencyPolicy
from .studio_dependencies_policy import StudioDependencyPolicy

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
                 max_duration=None,
                 owner=None):

        self.key = key
        self.args = []
        self.filename = filename
        self.owner = owner if owner else None

        if filename and '::' in filename:
            self.filename = '-m'
            module_name = filename.replace('::', '.')
            if module_name.startswith('.'):
                module_name = module_name[1:]

            self.args.append(module_name)

        if args:
            self.args += args

        self.args = [shquote(a) for a in self.args]

        self.pythonenv = pythonenv
        self.project = project
        self.pythonver = pythonver if pythonver else str(sys.version_info[0]) + '.' + str(sys.version_info[1])

        try:
            model_dir = fs_tracker.get_model_directory(key)
        except BaseException:
            model_dir = None

        std_artifacts_dict = {
            'workspace': {
                'mutable': False,
                'unpack': True
            },
            'modeldir': {
                'local': model_dir,
                'mutable': True,
                'unpack': True
            },
            'retval': {
                'local': fs_tracker.get_artifact_cache('retval', key),
                'mutable': True,
                'unpack': True
            },
            'output': {
                'local': fs_tracker.get_artifact_cache('output', key),
                'mutable': True,
                'unpack': True
            },
            'tb': {
                'local': fs_tracker.get_tensorboard_dir(key),
                'mutable': True,
                'unpack': True
            },
            '_metrics': {
                'local': fs_tracker.get_artifact_cache('_metrics', key),
                'mutable': True,
                'unpack': True
            },
            '_metadata': {
                'local': fs_tracker.get_artifact_cache('_metadata', key),
                'mutable': True,
                'unpack': True
            }
        }
        if artifacts is not None:
            for tag, art_dict in artifacts.items():
                art_update = std_artifacts_dict.get(tag, None)
                if art_update is not None:
                    art_dict.update(art_update)

        # Build table of experiment artifacts:
        self.artifacts = dict()
        for tag, art in artifacts.items():
            self.artifacts[tag] = Artifact(tag, art)

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

    def to_dict(self):
        result = dict()
        result['key'] = self.key
        result['args'] = self.args
        result['filename'] = self.filename
        result['pythonenv'] = self.pythonenv
        result['project'] = self.project
        result['pythonver'] = self.pythonver
        result['resources_needed'] = self.resources_needed
        result['status'] = self.status
        result['time_added'] = self.time_added
        result['time_started'] = self.time_started
        result['time_last_checkpoint'] = self.time_last_checkpoint
        result['time_finished'] = self.time_finished
        result['info'] = self.info
        result['git'] = self.git
        result['metric'] = self.metric
        result['max_duration'] = self.max_duration
        result['owner'] = self.owner

        # Process artifacts:
        artifacts_dict = dict()
        for art_name, art in self.artifacts.items():
            artifacts_dict[art_name] = art.to_dict()
        result['artifacts'] = artifacts_dict

        return result

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
        max_duration=None,
        dependency_policy: DependencyPolicy=None):

    key = experiment_name if experiment_name else \
        str(int(time.time())) + "_" + str(uuid.uuid4())

    if dependency_policy is None:
        dependency_policy = StudioDependencyPolicy()
    packages = dependency_policy.generate(resources_needed)

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
    try:
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
            max_duration=data.get('max_duration'),
            owner=data.get('owner')
        )
    except KeyError as e:
        raise e
