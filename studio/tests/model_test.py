import unittest
import inspect
import yaml
import uuid
import os
import time
import pip
import tempfile
import shutil

from studio import model
from studio.auth import remove_all_keys


def get_methods(cls):
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)
    return set([name for name, _ in methods if not name.startswith('_')])


class ProvidersTest(unittest.TestCase):

    def test_providers_compatible(self):
        # Check that all available providers are compatible.
        firebase_methods = get_methods(model.FirebaseProvider)
        postgres_methods = get_methods(model.PostgresProvider)
        self.assertEqual(firebase_methods, postgres_methods)


class FirebaseProviderTest(unittest.TestCase):
    def get_firebase_provider(self, config_name='test_config.yaml'):
        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        with open(config_file) as f:
            config = yaml.load(f)

        return model.get_db_provider(config)

    def test_get_set_firebase(self):
        fb = self.get_firebase_provider()
        response = fb.__getitem__("test/hello")
        self.assertEquals(response, "world")

        random_str = str(uuid.uuid4())
        key_path = 'test/randomKey'
        fb.__setitem__(key_path, random_str)

        self.assertTrue(fb.__getitem__(key_path) == random_str)
        fb._delete(key_path)

    def test_get_set_auth_firebase(self):
        remove_all_keys()
        fb = self.get_firebase_provider('test_config_auth.yaml')
        response = fb.__getitem__("authtest/hello")
        self.assertEquals(response, "world")

        random_str = str(uuid.uuid4())
        key_path = 'authtest/randomKey'
        fb.__setitem__(key_path, random_str)

        self.assertTrue(fb.__getitem__(key_path) == random_str)
        fb._delete(key_path)
        remove_all_keys()

    def test_get_set_noauth_firebase(self):
        remove_all_keys()
        fb = self.get_firebase_provider('test_config.yaml')
        response = fb.__getitem__("authtest/hello")
        self.assertTrue(response is None)

        random_str = str(uuid.uuid4())
        key_path = 'authtest/randomKey'
        fb.__setitem__(key_path, random_str)
        self.assertTrue(fb.__getitem__(key_path) is None)
        remove_all_keys()

    def test_get_set_firebase_bad(self):
        # smoke test to make sure access to a database at wrong
        # url is reported, but does not crash the system
        fb = self.get_firebase_provider('test_bad_config.yaml')
        response = fb.__getitem__("test/hello")
        self.assertTrue(response is None)

        fb.__setitem__("test/hello", "bla")

    def test_upload_download_file(self):
        fb = self.get_firebase_provider()
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('tests/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file('tests/test_upload_download.txt')
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file_auth(self):
        remove_all_keys()
        fb = self.get_firebase_provider('test_config_auth.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('authtest/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)

        # test an authorized attempt to delete file
        remove_all_keys()
        fb = self.get_firebase_provider('test_config.yaml')
        fb._delete_file('authtest/test_upload_download.txt')
        remove_all_keys()
        fb = self.get_firebase_provider('test_config_auth.yaml')
        # to make sure file is intact and the same as we uploaded

        fb._download_file('authtest/test_upload_download.txt', tmp_filename)

        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file('authtest/test_upload_download.txt')
        fb._download_file('authtest/test_upload_download.txt', tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file_noauth(self):
        remove_all_keys()
        fb = self.get_firebase_provider('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('authtest/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)
        fb._download_file('authtest/test_upload_download.txt', tmp_filename)

        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file_bad(self):
        # smoke test to make sure attempt to access a wrong file
        # in the database is wrapped and does not crash the system
        fb = self.get_firebase_provider('test_bad_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('tests/test_upload_download.txt', tmp_filename)
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)

    def test_upload_download_dir(self):
        fb = self.get_firebase_provider()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        random_str = str(uuid.uuid4())

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', 'test_upload_download.txt')
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_dir('tests/test_upload_download_dir.tgz', tmp_dir)
        shutil.rmtree(tmp_dir)
        fb._download_dir('tests/test_upload_download_dir.tgz', tmp_dir)

        with open(tmp_filename, 'r') as f:
            line = f.read()

        shutil.rmtree(tmp_dir)
        self.assertTrue(line == random_str)

    def test_get_user_keybase(self):
        fb = self.get_firebase_provider()
        keybase = fb._get_user_keybase()
        self.assertTrue(keybase == 'users/guest/')

    def test_get_experiments_keybase(self):
        fb = self.get_firebase_provider()
        keybase = fb._get_experiments_keybase()
        self.assertTrue(keybase == 'experiments/')

    def test_get_projects_keybase(self):
        fb = self.get_firebase_provider()
        keybase = fb._get_projects_keybase()
        self.assertTrue(keybase == 'projects/')

    def test_add_experiment(self):
        fb = self.get_firebase_provider()
        experiment, experiment_name, _, _ = get_test_experiment()

        fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
        fb.add_experiment(experiment)

        self.assertTrue(experiment.status == 'waiting')
        self.assertTrue(experiment.time_added <= time.time())
        actual_experiment_dict = fb.__getitem__(
            fb._get_experiments_keybase() + '/' + experiment_name)
        for key, value in experiment.__dict__.iteritems():
            if value:
                self.assertTrue(actual_experiment_dict[key] == value)

        fb.finish_experiment(experiment)

    def test_start_experiment(self):
        fb = self.get_firebase_provider()
        experiment, experiment_name, _, _ = get_test_experiment()

        fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
        fb.add_experiment(experiment)
        fb.start_experiment(experiment)

        self.assertTrue(experiment.status == 'running')
        self.assertTrue(experiment.time_added <= time.time())
        self.assertTrue(experiment.time_started <= time.time())

        actual_experiment_dict = fb.__getitem__(
            fb._get_experiments_keybase() + '/' + experiment_name)
        for key, value in experiment.__dict__.iteritems():
            if value:
                self.assertTrue(actual_experiment_dict[key] == value)

        fb.finish_experiment(experiment)

    def test_finish_experiment(self):
        fb = self.get_firebase_provider()
        experiment, experiment_name, _, _ = get_test_experiment()

        fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
        fb.add_experiment(experiment)
        fb.start_experiment(experiment)
        fb.finish_experiment(experiment)

        self.assertTrue(experiment.status == 'finished')
        self.assertTrue(experiment.time_added <= time.time())
        self.assertTrue(experiment.time_started <= time.time())
        self.assertTrue(experiment.time_finished <= time.time())

        actual_experiment_dict = fb.__getitem__(
            fb._get_experiments_keybase() + '/' + experiment_name)
        for key, value in experiment.__dict__.iteritems():
            if value:
                self.assertTrue(actual_experiment_dict[key] == value)

    def test_checkpoint_experiment(self):
        fb = self.get_firebase_provider()
        experiment, experiment_name, _, _, = get_test_experiment()

        if os.path.exists(experiment.model_dir):
            shutil.rmtree(experiment.model_dir)

        os.makedirs(experiment.model_dir)
        fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
        fb.add_experiment(experiment)
        fb.start_experiment(experiment)

        file_in_modeldir = os.path.join(
            experiment.model_dir, str(uuid.uuid4()))
        random_str = str(uuid.uuid4())
        with open(file_in_modeldir, 'w') as f:
            f.write(random_str)

        checkpoint_threads = fb.checkpoint_experiment(experiment)
        for t in checkpoint_threads:
            t.join()

        shutil.rmtree(experiment.model_dir)
        fb._download_modeldir(experiment_name)

        with open(file_in_modeldir, 'r') as f:
            line = f.read()

        self.assertTrue(line == random_str)

    def test_get_model_info(self):
        # TODO implement _get_model_info test
        pass


def get_test_experiment():
    filename = 'test.py'
    args = ['a', 'b', 'c']
    experiment_name = 'test_experiment'
    experiment = model.create_experiment(filename, args, experiment_name)
    return experiment, experiment_name, filename, args


class ModelTest(unittest.TestCase):
    def test_create_experiment(self):
        _, experiment_name, filename, args = get_test_experiment()
        experiment_project = 'create_experiment_project'
        experiment = model.create_experiment(
            filename, args, experiment_name, experiment_project)
        packages = [
            p._key +
            '==' +
            p._version for p in pip.pip.get_installed_distributions(
                local_only=True)]

        self.assertTrue(experiment.key == experiment_name)
        self.assertTrue(experiment.filename == filename)
        self.assertTrue(experiment.args == args)
        self.assertTrue(experiment.project == experiment_project)
        self.assertTrue(experiment.pythonenv == packages)

    def test_remove_backspaces(self):
        testline = 'abcd\x08\x08\x08efg\x08\x08hi\x08'
        removed = model._remove_backspaces(testline)
        self.assertTrue(removed == 'aeh')

        testline = 'abcd\x08\x08\x08efg\x08\x08hi'
        removed = model._remove_backspaces(testline)
        self.assertTrue(removed == 'aehi')

        testline = 'abcd'
        removed = model._remove_backspaces(testline)
        self.assertTrue(removed == 'abcd')

        testline = 'abcd\n\ndef'
        removed = model._remove_backspaces(testline)
        self.assertTrue(removed == testline)


if __name__ == "__main__":
    unittest.main()
