import unittest
import subprocess
import time
from random import randint
import os

from studio import model
from model_test import get_test_experiment


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google cloud')
class HTTPProviderTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys():
            return
        print "Setting up"
        self.port = randint(5000, 9000)

        # self.app.run(port=self.port, debug=True)
        # self.serverp.start()
        self.server_config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            'test_config_http_server.yaml')

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

        time.sleep(10)

    @classmethod
    def tearDownClass(self):
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys():
            return
        print "Tearing down"

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
