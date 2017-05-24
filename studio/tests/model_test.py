import unittest
import inspect
import sys
import yaml
import uuid

from studio import model


def get_methods(cls):
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)
    return set([name for name, _ in methods if not name.startswith('_')])


class ProvidersTest(unittest.TestCase):

    def test_providers_compatible(self):
        # Check that all available providers are compatible.
        firebase_methods = get_methods(model.FirebaseProvider)
        postgres_methods = get_methods(model.PostgresProvider)
        self.assertEqual(firebase_methods, postgres_methods)

    def get_firebase_provider(self):
        config_file = 'test_config.yaml'
        with open(config_file) as f:
            config = yaml.load(f)
       
        return model.FirebaseProvider(config['database'])

    def test_get_set(self):
        fb = self.get_firebase_provider()
        response = fb["test/hello"]
        self.assertTrue(response, "world")
        
        randomStr = str(uuid.uuid4())
        keyPath = 'test/randomKey'
        fb[keyPath] = randomStr

        self.assertTrue(fb[keyPath] == randomStr)
        fb._delete(keyPath)


if __name__ == "__main__":
    unittest.main()
