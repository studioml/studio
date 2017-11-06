import unittest
import os
import tempfile
import uuid

from studio import model
from model_test import get_test_experiment


class HTTPProviderHostedTest(unittest.TestCase):

    def get_db_provider(self, config_name):
        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        return model.get_db_provider(model.get_config(config_file))

    def test_add_get_delete_experiment(self):
        with self.get_db_provider('test_config_http_client.yaml') as hp:

            experiment_tuple = get_test_experiment()
            hp.add_experiment(experiment_tuple[0])
            experiment = hp.get_experiment(experiment_tuple[0].key)
            self.assertEquals(experiment.key, experiment_tuple[0].key)
            self.assertEquals(
                experiment.filename,
                experiment_tuple[0].filename)
            self.assertEquals(experiment.args, experiment_tuple[0].args)

            hp.delete_experiment(experiment_tuple[1])

            self.assertTrue(hp.get_experiment(experiment_tuple[1]) is None)

    def test_start_experiment(self):
        with self.get_db_provider('test_config_http_client.yaml') as hp:
            experiment_tuple = get_test_experiment()

            hp.add_experiment(experiment_tuple[0])
            hp.start_experiment(experiment_tuple[0])

            experiment = hp.get_experiment(experiment_tuple[1])

            self.assertTrue(experiment.status == 'running')

            self.assertEquals(experiment.key, experiment_tuple[0].key)
            self.assertEquals(
                experiment.filename,
                experiment_tuple[0].filename)
            self.assertEquals(experiment.args, experiment_tuple[0].args)

            hp.finish_experiment(experiment_tuple[0])
            hp.delete_experiment(experiment_tuple[1])

    def test_add_get_experiment_artifacts(self):
        experiment_tuple = get_test_experiment()
        e_experiment = experiment_tuple[0]
        e_artifacts = e_experiment.artifacts

        a1_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        a2_filename = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))

        with open(a1_filename, 'w') as f:
            f.write('hello world')

        e_artifacts['a1'] = {
            'local': a1_filename,
            'mutable': False
        }

        e_artifacts['a2'] = {
            'local': a2_filename,
            'mutable': True
        }

        with self.get_db_provider('test_config_http_client.yaml') as db:
            db.add_experiment(e_experiment)

            experiment = db.get_experiment(e_experiment.key)
            self.assertEquals(experiment.key, e_experiment.key)
            self.assertEquals(experiment.filename, e_experiment.filename)
            self.assertEquals(experiment.args, e_experiment.args)
            db.delete_experiment(e_experiment.key)
            os.remove(a1_filename)


if __name__ == '__main__':
    unittest.main()
