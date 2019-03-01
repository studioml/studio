import unittest
import inspect
import yaml
import uuid
import os
import time
import six
import shutil

from studio import model
from studio.firebase_provider import FirebaseProvider
from studio.postgres_provider import PostgresProvider
from studio.s3_provider import S3Provider
from studio.auth import remove_all_keys
from studio.util import has_aws_credentials

from model_test import get_test_experiment


def get_methods(cls):
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)
    return set([name for name, _ in methods if not name.startswith('_')])


class ProvidersTest(unittest.TestCase):

    def test_providers_compatible(self):
        # Check that all available providers are compatible.
        firebase_methods = get_methods(FirebaseProvider)
        postgres_methods = get_methods(PostgresProvider)
        s3_methods = get_methods(S3Provider)

        self.assertEqual(firebase_methods, postgres_methods)
        self.assertEqual(firebase_methods, s3_methods)


class KeyValueProviderTest(object):
    def get_default_config_name(self):
        return 'test_config.yaml'

    def get_provider(self, config_name=None):
        config_name = config_name if config_name else \
            self.get_default_config_name()

        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        with open(config_file) as f:
            config = yaml.load(f)

        return model.get_db_provider(config)

    def test_get_set(self):
        with self.get_provider() as fb:
            fb._set("test/hello", "world")
            response = fb._get("test/hello")
            self.assertEquals(response, "world")

            random_str = str(uuid.uuid4())
            key_path = 'test/randomKey'
            fb._set(key_path, random_str)

            self.assertTrue(fb._get(key_path) == random_str)
            fb._delete(key_path)

    def test_get_user_keybase(self):
        with self.get_provider() as fb:
            keybase = fb._get_user_keybase()
            self.assertTrue(keybase == 'users/guest/')

    def test_get_experiments_keybase(self):
        with self.get_provider() as fb:
            keybase = fb._get_experiments_keybase()
            self.assertTrue(keybase == 'experiments/')

    def test_get_projects_keybase(self):
        with self.get_provider() as fb:
            keybase = fb._get_projects_keybase()
            self.assertTrue(keybase == 'projects/')

    def test_add_experiment(self):
        with self.get_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + experiment_name)
            fb.add_experiment(experiment)

            self.assertTrue(experiment.status == 'waiting')
            self.assertTrue(experiment.time_added <= time.time())
            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.finish_experiment(experiment)
            fb.delete_experiment(experiment)

    def test_start_experiment(self):
        with self.get_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + experiment_name)
            fb.add_experiment(experiment)
            fb.start_experiment(experiment)

            self.assertTrue(experiment.status == 'running')
            self.assertTrue(experiment.time_added <= time.time())
            self.assertTrue(experiment.time_started <= time.time())

            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.finish_experiment(experiment)
            fb.delete_experiment(experiment)

    def test_finish_experiment(self):
        with self.get_provider() as fb:
            experiment, experiment_name, _, _ = get_test_experiment()

            fb._delete(fb._get_experiments_keybase() + experiment_name)
            fb.add_experiment(experiment)
            fb.start_experiment(experiment)
            fb.finish_experiment(experiment)

            self.assertTrue(experiment.status == 'finished')
            self.assertTrue(experiment.time_added <= time.time())
            self.assertTrue(experiment.time_started <= time.time())
            self.assertTrue(experiment.time_finished <= time.time())

            actual_experiment_dict = fb._get(
                fb._get_experiments_keybase() + experiment_name)
            for key, value in six.iteritems(experiment.__dict__):
                if value:
                    self.assertTrue(actual_experiment_dict[key] == value)

            fb.delete_experiment(experiment)

    def test_checkpoint_experiment(self):
        with self.get_provider() as fb:
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


class FirebaseProviderTest(unittest.TestCase, KeyValueProviderTest):
    _multiprocess_shared_ = True

    def test_get_set_auth_firebase(self):
        remove_all_keys()
        with self.get_provider('test_config_auth.yaml') as fb:
            response = fb._get("authtest/hello")
            self.assertEquals(response, "world")

            random_str = str(uuid.uuid4())
            key_path = 'authtest/randomKey'
            fb._set(key_path, random_str)

            self.assertTrue(fb._get(key_path) == random_str)
            fb._delete(key_path)
            remove_all_keys()

    def test_get_set_noauth_firebase(self):
        remove_all_keys()
        with self.get_provider('test_config.yaml') as fb:
            response = fb._get("authtest/hello")
            self.assertTrue(response is None)

            random_str = str(uuid.uuid4())
            key_path = 'authtest/randomKey'
            fb._set(key_path, random_str)
            self.assertTrue(fb._get(key_path) is None)
            remove_all_keys()

    def test_get_set_firebase_bad(self):
        # smoke test to make sure access to a database at wrong
        # url is reported, but does not crash the system
        with self.get_provider('test_bad_config.yaml') as fb:
            response = fb._get("test/hello")
            self.assertTrue(response is None)

            fb._set("test/hello", "bla")


@unittest.skipIf(
    not has_aws_credentials(),
    'AWS credentials not found, cannot run test')
class S3ProviderTest(unittest.TestCase, KeyValueProviderTest):
    _multiprocess_shared_ = True

    def get_default_config_name(self):
        return 'test_config_s3.yaml'


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'google app credentials not found, cannot run test')
class GSProviderTest(unittest.TestCase, KeyValueProviderTest):
    def get_default_config_name(self):
        return 'test_config_gs.yaml'


if __name__ == "__main__":
    unittest.main()
