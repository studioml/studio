import unittest
import inspect
import sys

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
        dbUrl = "https://studio-ed756.firebaseio.com/"
        dbSecret = "3NE3ONN9CJgjqhC5Ijlr9DTNXmmyladvKhD2AbLk"
        return model.FirebaseProvider(dbUrl, dbSecret)

    def test_firebase_get(self):
        fb = self.get_firebase_provider()
        response = fb.db.get("test/hello", None)
        self.assertTrue(response, "world")

        response = fb.db.get("test/", "hello")
        self.assertTrue(response, "world")


if __name__ == "__main__":
    unittest.main()
