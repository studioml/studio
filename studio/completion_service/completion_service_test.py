import uuid
import unittest
import os
import logging
from multiprocessing.pool import ThreadPool

from .completion_service import CompletionService

from studio.util import has_aws_credentials


logging.basicConfig()


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
        with CompletionService(experimentId, config=config_path,
                               cloud_timeout=10) as cs:
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
        not has_aws_credentials(),
        'Need to have aws credentials to use EC2')
    def test_1k_experiments_ec2(self):
        experimentId = str(uuid.uuid4())
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        n_experiments = 1000
        num_workers = 60
        results = {}
        expected_results = {}

        logger = logging.getLogger('test_1k_experiments_ec2')
        logger.setLevel(10)

        with CompletionService(experimentId,
                               config=config_path, cloud='ec2spot',
                               num_workers=num_workers) as cs:
            pool = ThreadPool(16)

            def submit_task(i):
                key = cs.submitTaskWithFiles(
                    os.path.join(
                        mypath,
                        'completion_service_func.py'),
                    [i],
                    {
                        'a': '/Users/peter.zhokhov/.bash_profile',
                        'p': '/Users/peter.zhokhov/.bash_profile'
                    })
                logger.info('Submitted task ' + str(i))
                expected_results[key] = [i]

            pool.map(submit_task, range(n_experiments))

            for i in range(0, n_experiments):
                result = cs.getResults(blocking=True)
                logger.info('Received result ' + str(result))
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
