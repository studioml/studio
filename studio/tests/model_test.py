import unittest
import inspect
import yaml
import uuid
import os
import time
import pip
import shutil
import six

from studio import model
from studio.firebase_provider import FirebaseProvider
from studio.postgres_provider import PostgresProvider
from studio.auth import remove_all_keys
from studio.experiment import create_experiment


def get_methods(cls):
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)
    return set([name for name, _ in methods if not name.startswith('_')])


class ProvidersTest(unittest.TestCase):

    def test_providers_compatible(self):
        # Check that all available providers are compatible.
        firebase_methods = get_methods(FirebaseProvider)
        postgres_methods = get_methods(PostgresProvider)
        self.assertEqual(firebase_methods, postgres_methods)


class FirebaseProviderTest(unittest.TestCase):
    _multiprocess_can_split_ = True

    def get_firebase_provider(self, config_name='test_config.yaml'):
        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        with open(config_file) as f:
            config = yaml.load(f)

        return model.get_db_provider(config)

    def test_get_set_firebase(self):
        with self.get_firebase_provider() as fb:
            response = fb._get("test/hello")
            self.assertEquals(response, "world")

            random_str = str(uuid.uuid4())
            key_path = 'test/randomKey'
            fb.__setitem__(key_path, random_str)

            self.assertTrue(fb._get(key_path) == random_str)
            fb._delete(key_path)

    def test_get_set_auth_firebase(self):
        remove_all_keys()
        with self.get_firebase_provider('test_config_auth.yaml') as fb:
            response = fb._get("authtest/hello")
            self.assertEquals(response, "world")

            random_str = str(uuid.uuid4())
            key_path = 'authtest/randomKey'
            fb.__setitem__(key_path, random_str)

            self.assertTrue(fb._get(key_path) == random_str)
            fb._delete(key_path)
            remove_all_keys()

    def test_get_set_noauth_firebase(self):
        remove_all_keys()
        with self.get_firebase_provider('test_config.yaml') as fb:
            response = fb._get("authtest/hello")
            self.assertTrue(response is None)

            random_str = str(uuid.uuid4())
            key_path = 'authtest/randomKey'
            fb.__setitem__(key_path, random_str)
            self.assertTrue(fb._get(key_path) is None)
            remove_all_keys()

    def test_get_set_firebase_bad(self):
        # smoke test to make sure access to a database at wrong
        # url is reported, but does not crash the system
        with self.get_firebase_provider('test_bad_config.yaml') as fb:
            response = fb._get("test/hello")
            self.assertTrue(response is None)

            fb.__setitem__("test/hello", "bla")

    def test_get_user_keybase(self):
        with self.get_firebase_provider() as fb:
            keybase = fb._get_user_keybase()
            self.assertTrue(keybase == 'users/guest/')

    def test_get_experiments_keybase(self):
        with self.get_firebase_provider() as fb:
            keybase = fb._get_experiments_keybase()
            self.assertTrue(keybase == 'experiments/')

    def test_get_projects_keybase(self):
        with self.get_firebase_provider() as fb:
            keybase = fb._get_projects_keybase()
            self.assertTrue(keybase == 'projects/')

    def test_add_experiment(self):
        with self.get_firebase_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
            fb.add_experiment(experiment)

            self.assertTrue(experiment.status == 'waiting')
            self.assertTrue(experiment.time_added <= time.time())
            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + '/' + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.finish_experiment(experiment)
            fb.delete_experiment(experiment)

    def test_start_experiment(self):
        with self.get_firebase_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
            fb.add_experiment(experiment)
            fb.start_experiment(experiment)

            self.assertTrue(experiment.status == 'running')
            self.assertTrue(experiment.time_added <= time.time())
            self.assertTrue(experiment.time_started <= time.time())

            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + '/' + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.finish_experiment(experiment)
            fb.delete_experiment(experiment)

    def test_finish_experiment(self):
        with self.get_firebase_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + '/' + experiment_name)
            fb.add_experiment(experiment)
            fb.start_experiment(experiment)
            fb.finish_experiment(experiment)

            self.assertTrue(experiment.status == 'finished')
            self.assertTrue(experiment.time_added <= time.time())
            self.assertTrue(experiment.time_started <= time.time())
            self.assertTrue(experiment.time_finished <= time.time())

            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + '/' + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.delete_experiment(experiment)

    def test_checkpoint_experiment(self):
        with self.get_firebase_provider() as fb:
            experiment, experiment_name, _, _, = get_test_experiment()

            modeldir = experiment.artifacts['modeldir']['local']
            if os.path.exists(modeldir):
                shutil.rmtree(modeldir)

            os.makedirs(modeldir)
            try:
                fb.delete_experiment(experiment_name)
            except BaseException:
                pass

            fb.add_experiment(experiment)
            fb.start_experiment(experiment)

            file_in_modeldir = os.path.join(modeldir, str(uuid.uuid4()))
            random_str = str(uuid.uuid4())
            with open(file_in_modeldir, 'w') as f:
                f.write(random_str)

            checkpoint_threads = fb.checkpoint_experiment(experiment)
            if checkpoint_threads:
                for t in checkpoint_threads:
                    t.join()

            shutil.rmtree(modeldir)
            fb.store.get_artifact(
                fb.get_experiment(
                    experiment_name,
                    getinfo=False).artifacts['modeldir'])

            with open(file_in_modeldir, 'r') as f:
                line = f.read()

            self.assertTrue(line == random_str)
            fb.delete_experiment(experiment)


def get_test_experiment():
    filename = 'test.py'
    args = ['a', 'b', 'c']
    experiment_name = 'test_experiment_' + str(uuid.uuid4())
    experiment = create_experiment(filename, args, experiment_name)
    return experiment, experiment_name, filename, args


class ModelTest(unittest.TestCase):
    def test_create_experiment(self):
        _, experiment_name, filename, args = get_test_experiment()
        experiment_project = 'create_experiment_project'
        experiment = create_experiment(
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

    def test_get_config_env(self):
        value1 = str(uuid.uuid4())
        os.environ['TEST_VAR1'] = value1
        value2 = str(uuid.uuid4())
        os.environ['TEST_VAR2'] = value2

        config = model.get_config(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         'test_config_env.yaml'))
        self.assertEquals(config['test_key'], value1)
        self.assertEquals(config['test_section']['test_key'], value2)


if __name__ == "__main__":
    unittest.main()
