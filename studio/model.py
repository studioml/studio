"""Data providers."""

import os
import pip
import uuid

import yaml
import pyrebase
import logging
import time
import glob
import tempfile
import re
import StringIO
from threading import Thread
import subprocess
import requests
import json
import hashlib
import shutil

from tensorflow.contrib.framework.python.framework import checkpoint_utils

import fs_tracker
from auth import FirebaseAuth
from model_util import KerasModelWrapper

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
                 info={}):

        self.key = key
        self.filename = filename
        self.args = args if args else []
        self.pythonenv = pythonenv
        self.project = project
        workspace_path = '.'
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
                'local': model_dir + "/output.log",
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

    def get_model(self):
        if self.info.get('type') == 'keras':
            hdf5_files = [
                (p, os.path.getmtime(p))
                for p in
                glob.glob(self.artifacts['modeldir'] + '/*.hdf*') +
                glob.glob(self.artifacts['modeldir'] + '/*.h5')]

            last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
            return KerasModelWrapper(last_checkpoint)

        if self.info.get('type') == 'tensorflow':
            raise NotImplementedError

        raise ValueError("Experiment type is unknown!")


def create_experiment(
        filename,
        args,
        experiment_name=None,
        project=None,
        artifacts={},
        resources_needed=None):
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
        resources_needed=resources_needed)


class FirebaseProvider(object):
    """Data provider for Firebase."""

    def __init__(self, database_config, blocking_auth=True):
        guest = database_config.get('guest')

        self.app = pyrebase.initialize_app(database_config)
        self.logger = logging.getLogger('FirebaseProvider')
        self.logger.setLevel(10)

        self.auth = FirebaseAuth(self.app,
                                 database_config.get("use_email_auth"),
                                 database_config.get("email"),
                                 database_config.get("password"),
                                 blocking_auth) \
            if not guest else None

        if self.auth and not self.auth.expired:
            self.__setitem__(self._get_user_keybase() + "email",
                             self.auth.get_user_email())

    def __getitem__(self, key):
        try:
            splitKey = key.split('/')
            key_path = '/'.join(splitKey[:-1])
            key_name = splitKey[-1]
            dbobj = self.app.database().child(key_path).child(key_name)
            return dbobj.get(self.auth.get_token()).val() if self.auth \
                else dbobj.get().val()
        except Exception as err:
            self.logger.error(("Getting key {} from a database " +
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
            self.logger.error(("Putting key {}, value {} into a database " +
                               "raised an exception: {}")
                              .format(key, value, err))

    def _upload_file(self, key, local_file_path):
        try:
            storageobj = self.app.storage().child(key)
            if self.auth:
                storageobj.put(local_file_path, self.auth.get_token())
            else:
                storageobj.put(local_file_path)
        except Exception as err:
            self.logger.error(("Uploading file {} with key {} into storage " +
                               "raised an exception: {}")
                              .format(local_file_path, key, err))

    def _download_file(self, key, local_file_path):
        self.logger.debug("Downloading file at key {} to local path {}..."
                          .format(key, local_file_path))
        try:
            storageobj = self.app.storage().child(key)

            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
                escaped_key = key.replace('/', '%2f')
                url = "{}/o/{}?alt=media".format(
                    self.app.storage().storage_bucket,
                    escaped_key)

                response = requests.get(url, stream=True, headers=headers)
                if response.status_code == 200:
                    with open(local_file_path, 'wb') as f:
                        for chunk in response:
                            f.write(chunk)
                else:
                    raise ValueError("Response error with code {}"
                                     .format(response.status_code))
            else:
                storageobj.download(local_file_path)
            self.logger.debug("Done")
        except Exception as err:
            self.logger.error(
                ("Downloading file {} to local path {} from storage " +
                 "raised an exception: {}") .format(
                    key,
                    local_file_path,
                    err))

    def _delete_file(self, key):
        self.logger.debug("Downloading file at key {}".format(key))
        try:
            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
            else:
                headers = {}

            escaped_key = key.replace('/', '%2f')
            url = "{}/o/{}?alt=media".format(
                self.app.storage().storage_bucket,
                escaped_key)

            response = requests.delete(url, headers=headers)
            if response.status_code != 204:
                raise ValueError("Response error with code {}"
                                 .format(response.status_code))

            self.logger.debug("Done")
        except Exception as err:
            self.logger.error(
                ("Deleting file {} from storage " +
                 "raised an exception: {}") .format(key, err))

    def _get_file_url(self, key):
        self.logger.debug("Getting a download url for a file at key {}"
                          .format(key))
        try:
            if self.auth:
                # pyrebase download does not work with files that require
                # authentication...
                # Need to rewrite
                # storageobj.download(local_file_path, self.auth.get_token())

                headers = {"Authorization": "Firebase " +
                           self.auth.get_token()}
            else:
                headers = {}

            escaped_key = key.replace('/', '%2f')
            url = "{}/o/{}".format(
                self.app.storage().storage_bucket,
                escaped_key)

            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise ValueError("Response error with code {}"
                                 .format(response.status_code))

            self.logger.debug("Done")
            return url + '?alt=media&token=' \
                + json.loads(response.content)['downloadTokens']
        except Exception as err:
            self.logger.error(
                ("Getting url of file {} " +
                 "raised an exception: {}") .format(key, err))

    def _upload_dir(self, local_path, key=None, background=False, cache=True):
        if os.path.exists(local_path):
            tar_filename = os.path.join(tempfile.gettempdir(),
                                        str(uuid.uuid4()))

            local_path = re.sub('/\Z', '', local_path)
            local_nameonly = re.sub('.*/', '', local_path)
            local_basepath = re.sub('/[^/]*\Z', '', local_path)

            if cache and key:
                cache_dir = fs_tracker.get_artifact_cache(key)
                if cache_dir != local_path:
                    self.logger.debug(
                        "Copying local path {} to cache {}"
                        .format(local_path, cache_dir))

                    if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
                        shutil.rmtree(cache_dir)

                    subprocess.call(['cp', '-pR', local_path, cache_dir])

            self.logger.debug(
                ("Tarring and uploading directrory. " +
                 "tar_filename = {}, " +
                 "local_path = {}, " +
                 "key = {}").format(
                    tar_filename,
                    local_path,
                    key))

            tarcmd = 'tar -czf {} -C {} {}'.format(
                tar_filename,
                local_basepath,
                local_nameonly)

            self.logger.debug("Tar cmd = {}".format(tarcmd))

            subprocess.call(['/bin/bash', '-c', tarcmd])

            if key is None:
                key = 'blobstore/' + sha256_checksum(tar_filename) + '.tgz'

            def finish_upload():
                self._upload_file(key, tar_filename)
                os.remove(tar_filename)

            t = Thread(target=finish_upload)
            t.start()

            if background:
                return (key, t)
            else:
                t.join()
                return key
        else:
            self.logger.debug(("Local path {} does not exist. " +
                               "Not uploading anything.").format(local_path))

    def _download_dir(self, local_path, key, background=False):
        local_path = re.sub('\/\Z', '', local_path)
        local_basepath = re.sub('\/[^\/]*\Z', '', local_path)

        # TODO add a check if download is required (if the directory is newer
        # than remote, we can skip the download )

        self.logger.debug("Downloading dir {} to local path {} from storage..."
                          .format(key, local_path))
        tar_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        self.logger.debug("tar_filename = {} ".format(tar_filename))

        def finish_download():
            self._download_file(key, tar_filename)
            if os.path.exists(tar_filename):
                # first, figure out if the tar file has a base path of .
                # or not
                self.logger.debug("Untarring {}".format(tar_filename))
                listtar, _ = subprocess.Popen(['tar', '-tzf', tar_filename],
                                              stdout=subprocess.PIPE
                                              ).communicate()
                listtar = listtar.strip().split('\n')
                self.logger.debug('List of files in the tar: ' + str(listtar))
                if listtar[0].startswith('./'):
                    # Files are archived into tar from .; adjust path
                    # accordingly
                    basepath = local_path
                else:
                    basepath = local_basepath

                subprocess.call([
                    '/bin/bash',
                    '-c',
                    ('mkdir -p {} &&' +
                     'tar -xzf {} -C {} --keep-newer-files')
                    .format(basepath, tar_filename, basepath)])

                if len(listtar) == 1:
                    actual_path = os.path.join(basepath, listtar[0])
                    self.logger.info(
                        'Renaming {} into {}'.format(
                            actual_path, local_path))
                    os.rename(actual_path, local_path)
            else:
                self.logger.error(
                    'file {} download failed'.format(tar_filename))

        t = Thread(target=finish_download)
        t.start()
        if background:
            return t
        else:
            t.join()

        # os.remove(tar_filename)

    def _delete(self, key):
        dbobj = self.app.database().child(key)

        if self.auth:
            dbobj.remove(self.auth.get_token())
        else:
            dbobj.remove()

    def _get_user_keybase(self, userid=None):
        if not userid:
            if not self.auth:
                userid = 'guest'
            else:
                userid = self.auth.get_user_id()

        return "users/" + userid + "/"

    def _get_experiments_keybase(self, userid=None):
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def add_experiment(self, experiment):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'

        for tag, art in experiment.artifacts.iteritems():
            if art['mutable']:
                art['key'] = self._get_experiments_keybase() + \
                    experiment.key + '/' + tag + '.tgz'
            else:
                if art['local'] is not None:
                    # upload immutable artifacts
                    blobkey = self._upload_dir(art['local'])
                    art['key'] = blobkey

        self.__setitem__(self._get_experiments_keybase() + experiment.key,
                         experiment.__dict__)

        self.__setitem__(self._get_user_keybase() + "experiments/" +
                         experiment.key,
                         experiment.key)

        if experiment.project and self.auth:
            self.__setitem__(self._get_projects_keybase() +
                             experiment.project + "/" +
                             experiment.key + "/userId",
                             self.auth.get_user_id())

        self.checkpoint_experiment(experiment, blocking=True)

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

    def finish_experiment(self, experiment):
        self.checkpoint_experiment(experiment, blocking=True)
        experiment.status = 'finished'
        experiment.time_finished = time.time()
        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/status",
                         "finished")

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_finished",
                         experiment.time_finished)

    def delete_experiment(self, experiment_key):
        experiment = self.get_experiment(experiment_key, getinfo=False)
        self._delete(self._get_user_keybase() + 'experiments/' +
                     experiment_key)

        for key in experiment.artifacts.keys():
            self._delete_file(self._get_experiments_keybase() +
                              experiment_key + '/' + key + '.tgz')

        self._delete(self._get_experiments_keybase() + experiment_key)

    def checkpoint_experiment(self, experiment, blocking=False):
        checkpoint_threads = [
            Thread(
                target=self._upload_dir,
                args=(art['local'], art['key']))
            for _, art in experiment.artifacts.iteritems()
            if art['mutable']]

        for t in checkpoint_threads:
            t.start()
            t.join()

        self.__setitem__(self._get_experiments_keybase() +
                         experiment.key + "/time_last_checkpoint",
                         time.time())
        if blocking:
            for t in checkpoint_threads:
                pass
                # t.join()
        else:
            return checkpoint_threads

    def _experiment(self, key, data, info={}):
        return Experiment(
            key=key,
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
            info=info
        )

    def _download_modeldir(self, key):
        self.logger.info("Downloading model directory...")
        self._download_dir(fs_tracker.get_model_directory(key),
                           self._get_experiments_keybase() +
                           key + '/modeldir.tgz')
        self.logger.info("Done")

    def _get_experiment_info(self, key):
        self._download_modeldir(key)
        local_modeldir = fs_tracker.get_model_directory(key)
        info = {}
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

        if not type_found:
            info['type'] = 'unknown'

        # TODO: get the name of a log file from config
        logpath = os.path.join(
            fs_tracker.get_model_directory(key), 'output.log')

        if os.path.exists(logpath):
            tailp = subprocess.Popen(
                ['tail', '-50', logpath], stdout=subprocess.PIPE)
            stdoutdata = tailp.communicate()[0]
            logtail = _remove_backspaces(stdoutdata).split('\n')
            info['logtail'] = logtail

        return info

    def get_experiment(self, key, getinfo=True):
        data = self.__getitem__(self._get_experiments_keybase() + key)
        info = self._get_experiment_info(key) if getinfo else {}
        assert data, "data at path %s not found! " % (
            self._get_experiments_keybase() + key)
        return self._experiment(key, data, info)

    def get_user_experiments(self, userid=None):
        experiment_keys = self.__getitem__(
            self._get_user_keybase(userid) + "/experiments")
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(experiment_keys.keys())

    def get_project_experiments(self, project):
        experiment_keys = self.__getitem__(self._get_projects_keybase()
                                           + project)
        if not experiment_keys:
            experiment_keys = {}
        return self._get_valid_experiments(experiment_keys.keys())

    def get_artifacts(self, key):
        experiment = self.get_experiment(key, getinfo=False)
        base = self._get_experiments_keybase() + key
        return {
            key: self._get_file_url(base + '/' + key + '.tgz') for
            key in experiment.artifacts.keys()
        }

    def _get_valid_experiments(self, experiment_keys):
        experiments = []
        for key in experiment_keys:
            try:
                experiment = self.get_experiment(key, getinfo=False)
                experiments.append(experiment)
            except AssertionError:
                self.logger.warn(
                    ("Experiment {} does not exist " +
                     "or is corrupted, deleting record").format(key))
                try:
                    self.delete_experiment(key)
                except BaseException:
                    pass
        return experiments

    def get_projects(self):
        return self.__getitem__(self._get_projects_keybase())

    def get_users(self):
        return self.__getitem__('users/')

    def refresh_auth_token(self, email, refresh_token):
        if self.auth:
            self.auth.refresh_token(email, refresh_token)

    def get_auth_domain(self):
        return self.app.auth_domain

    def is_auth_expired(self):
        if self.auth:
            return self.auth.expired
        else:
            return False


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

    def get_users(self):
        raise NotImplementedError()

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()

    def refresh_auth_token(self, email, refresh_token):
        raise NotImplementedError()

    def get_auth_domain(self):
        raise NotImplementedError()

    def is_auth_expired(self):
        raise NotImplementedError()


def get_config(config_file=None):
    def_config_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "default_config.yaml")
    with open(def_config_file) as f:
        config = yaml.load(f.read())

    if config_file:
        with open(config_file) as f:
            config.update(yaml.load(f.read()))

    return config


def get_db_provider(config=None, blocking_auth=True):
    if not config:
        config = get_config()
    assert 'database' in config.keys()
    db_config = config['database']
    assert db_config['type'].lower() == 'firebase'.lower()

    if 'projectId' in db_config.keys():
        projectId = db_config['projectId']
        db_config['authDomain'] = db_config['authDomain'].format(projectId)
        db_config['databaseURL'] = db_config['databaseURL'].format(projectId)
        db_config['storageBucket'] = db_config['storageBucket'].format(
            projectId)

    return FirebaseProvider(db_config, blocking_auth)


def _remove_backspaces(line):
    splitline = re.split('(\x08+)', line)
    buf = StringIO.StringIO()
    for i in range(0, len(splitline) - 1, 2):
        buf.write(splitline[i][:-len(splitline[i + 1])])

    if len(splitline) % 2 == 1:
        buf.write(splitline[-1])

    return buf.getvalue()


def sha256_checksum(filename, block_size=65536):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()
