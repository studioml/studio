import uuid
import unittest
import os
from .completion_service import CompletionService


class CompletionServiceTest(unittest.TestCase):

    def test_two_experiments(self):
        experimentId = str(uuid.uuid4())
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        n_experiments = 2
        results = {}
        expected_results = {}
        with CompletionService(experimentId, config=config_path) as cs:
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

        n_experiments = 2
        results = {}
        expected_results = {}
        with CompletionService(experimentId,
                               config=config_path, cloud='gcspot') as cs:
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

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS env variable to' +
        'use google cloud')
    def test_two_experiments_gcloud_nonspot(self):
        experimentId = str(uuid.uuid4())
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        n_experiments = 2
        results = {}
        expected_results = {}
        with CompletionService(experimentId,
                               config=config_path, cloud='gcloud') as cs:
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


if __name__ == '__main__':
    unittest.main()
