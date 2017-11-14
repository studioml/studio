import sys
import uuid
import unittest
import os
import logging

from .completion_service import CompletionService

from studio.util import has_aws_credentials


logging.basicConfig()


class CompletionServiceTest(unittest.TestCase):

    _multiprocess_shared_ = True

    def test_two_experiments_with_cs_args(self, n_experiments=2, **kwargs):
        if not(any(kwargs)):
            return
        mypath = os.path.dirname(os.path.realpath(__file__))
        experimentId = str(uuid.uuid4())
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

    @unittest.skipIf(not has_aws_credentials(),
                     'AWS credentials needed for this test')
    def test_two_experiments_ec2(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config_http_client.yaml')

        self.test_two_experiments_with_cs_args(
            config=config_path,
            cloud_timeout=100,
            cloud='ec2')

    @unittest.skipIf(not has_aws_credentials(),
                     'AWS credentials needed for this test')
    def test_two_experiments_ec2spot(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config_http_client.yaml')

        self.test_two_experiments_with_cs_args(
            config=config_path,
            cloud_timeout=100,
            cloud='ec2spot')

    @unittest.skip('conflicts with other local runner tests,' +
                   'left for debugging purposes')
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
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config_http_client.yaml')

        self.test_two_experiments_with_cs_args(
            config=config_path,
            cloud='gcloud')

    @unittest.skip('TODO peterz scale down or fix')
    # @unittest.skipIf(not has_aws_credentials(),
    #                 'AWS credentials needed for this test')
    def test_many_experiments_ec2(self):
        experimentId = str(uuid.uuid4())
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config.yaml')

        n_experiments = 100
        num_workers = 30

        print("Executing {} tasks with {} workers"
              .format(n_experiments, num_workers))

        results = {}
        expected_results = {}

        logger = logging.getLogger('test_1k_experiments_ec2')
        logger.setLevel(10)

        with CompletionService(experimentId,
                               config=config_path, cloud='ec2spot',
                               num_workers=num_workers) as cs:

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

            '''
            pool.map(submit_task, range(n_experiments))
            print("Submitted")
            pool.close()
            pool.join()
            '''
            for i in range(n_experiments):
                submit_task(i)

            for i in range(0, n_experiments):
                print("Trying to get a result " + str(i))
                result = cs.getResults(blocking=True)
                logger.info('Received result ' + str(result))
                results[result[0]] = result[1]

        self.assertEquals(results, expected_results)

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
