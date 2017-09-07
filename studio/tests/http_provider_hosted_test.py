import unittest
import subprocess
import time
from random import randint
import os

from studio import model
from model_test import get_test_experiment


class HTTPProviderHostedTest(unittest.TestCase):


    def get_http_provider(self):
        return model.get_db_provider(model.get_config(
               'test_config_http_client.yaml'))

    def get_firebase_provider(self):
        return model.get_db_provider(model.get_config('test_config.yaml'))

    def test_add_get_delete_experiment(self):
        with self.get_firebase_provider() as fp, \
             self.get_http_provider() as hp:

                experiment_tuple = get_test_experiment()
                hp.add_experiment(experiment_tuple[0])
                experiment = fp.get_experiment(experiment_tuple[0].key)
                self.assertEquals(experiment.key, experiment_tuple[0].key)
                self.assertEquals(experiment.filename, experiment_tuple[0].filename)
                self.assertEquals(experiment.args, experiment_tuple[0].args)

              
                fp.delete_experiment(experiment_tuple[1])
                
                try:
                    thrown = False
                    hp.get_experiment(experiment_tuple[1])
                except BaseException:
                    thrown = True
                self.assertTrue(thrown)

                experiment_tuple = get_test_experiment()
                fp.add_experiment(experiment_tuple[0])
                experiment = hp.get_experiment(experiment_tuple[0].key)
                self.assertEquals(experiment.key, experiment_tuple[0].key)
                self.assertEquals(experiment.filename, experiment_tuple[0].filename)
                self.assertEquals(experiment.args, experiment_tuple[0].args)

              
                hp.delete_experiment(experiment_tuple[1])

                try:
                    thrown = False
                    fp.get_experiment(experiment_tuple[1])
                except BaseException:
                    thrown = True
                self.assertTrue(thrown)
         

    def test_start_experiment(self):
        with self.get_http_provider() as hp:
            experiment_tuple = get_test_experiment()

            hp.add_experiment(experiment_tuple[0])
            hp.start_experiment(experiment_tuple[0])

            experiment = hp.get_experiment(experiment_tuple[1])

            self.assertTrue(experiment.status == 'running')
            self.assertTrue(experiment.time_added <= time.time())
            self.assertTrue(experiment.time_started <= time.time())

            self.assertEquals(experiment.key, experiment_tuple[0].key)
            self.assertEquals(experiment.filename, experiment_tuple[0].filename)
            self.assertEquals(experiment.args, experiment_tuple[0].args)

            hp.finish_experiment(experiment_tuple[0])
            hp.delete_experiment(experiment_tuple[1])


if __name__ == '__main__':
    unittest.main()
