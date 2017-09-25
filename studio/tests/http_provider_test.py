import unittest
import subprocess
import time
from random import randint
import os

from studio import model
from studio.util import has_aws_credentials
from model_test import get_test_experiment


@unittest.skipIf(not has_aws_credentials(),
                 "AWS credentials is missing, needed for " +
                 "server to communicate with storage")
class HTTPProviderTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        if not has_aws_credentials():
            return
        print("Starting up the API server")
        self.port = randint(5000, 9000)

        # self.app.run(port=self.port, debug=True)
        # self.serverp.start()
        self.server_config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            'test_config_http_server.yaml')

        print(self.server_config_file)

        self.client_config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            'test_config_http_client.yaml')

        self.serverp = subprocess.Popen([
            'studio-ui',
            '--port=' + str(self.port),
            '--verbose=debug',
            '--config=' + self.server_config_file,
            '--host=localhost'])

        time.sleep(25)

    @classmethod
    def tearDownClass(self):
        if not has_aws_credentials():
            return

        print("Shutting down the API server")
        self.serverp.kill()

    def get_db_provider(self):
        config = model.get_config(self.client_config_file)
        config['database']['serverUrl'] = 'http://localhost:' + str(self.port)
        return model.get_db_provider(config)

    def test_add_get_experiment(self):
        experiment_tuple = get_test_experiment()
        db = self.get_db_provider()
        db.add_experiment(experiment_tuple[0])

        experiment = db.get_experiment(experiment_tuple[0].key)
        self.assertEquals(experiment.key, experiment_tuple[0].key)
        self.assertEquals(experiment.filename, experiment_tuple[0].filename)
        self.assertEquals(experiment.args, experiment_tuple[0].args)

        db.delete_experiment(experiment_tuple[1])

    def test_start_experiment(self):
        db = self.get_db_provider()
        experiment_tuple = get_test_experiment()

        db.add_experiment(experiment_tuple[0])
        db.start_experiment(experiment_tuple[0])

        experiment = db.get_experiment(experiment_tuple[1])

        self.assertTrue(experiment.status == 'running')
        self.assertTrue(experiment.time_added <= time.time())
        self.assertTrue(experiment.time_started <= time.time())

        self.assertEquals(experiment.key, experiment_tuple[0].key)
        self.assertEquals(experiment.filename, experiment_tuple[0].filename)
        self.assertEquals(experiment.args, experiment_tuple[0].args)

        db.finish_experiment(experiment_tuple[0])
        db.delete_experiment(experiment_tuple[1])


if __name__ == '__main__':
    unittest.main()
