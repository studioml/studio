import uuid
import unittest
import os
from .completion_service import CompletionService


class CompletionServiceTest(unittest.TestCase):

    def test_two_experiments_with_cs_args(self, **kwargs):
        mypath = os.path.dirname(os.path.realpath(__file__))
        experimentId = str(uuid.uuid4())
        n_experiments = 2
        results = {}
        expected_results = {}
        with CompletionService(experimentId, **kwargs) as cs:
            for i in range(0, n_experiments):
                key = cs.submitTask(
                    os.path.join(
                        mypath,
                        'completion_service_func.py'),
                    [i])
                expected_results[key] = [i]

            for i in range(0, n_experiments):
                result = cs.getResults(blocking=True)
                results[result[0]] = result[1]

        self.assertEquals(results, expected_results)

    def test_two_experiments(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        self.test_two_experiments_with_cs_args(config=config_path)

    def test_two_experiments_apiserver(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config_http_client.yaml')

        self.test_two_experiments_with_cs_args(config=config_path)

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS env variable to' +
        'use google cloud')
    def test_two_experiments_gcloud(self):
        experimentId = str(uuid.uuid4())
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        self.test_two_experiments_with_cs_args(
            config=config_path,
            cloud='gcloud')

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS env variable to' +
        'use google cloud')
    def test_two_experiments_gcloud_nonspot(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        self.test_two_experiments_with_cs_args(
            config=config_path,
            cloud='gcloud')


if __name__ == '__main__':
    unittest.main()
