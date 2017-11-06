import sys
import unittest
import os
import uuid

from studio.gcloud_worker import GCloudWorkerManager
from studio.ec2cloud_worker import EC2WorkerManager
from local_worker_test import stubtest_worker

from timeout_decorator import timeout
from studio.util import has_aws_credentials


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google cloud')
class GCloudWorkerTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def get_worker_manager(self):
        project = 'studio-ed756'
        return GCloudWorkerManager(project)

    @timeout(500)
    def test_worker(self):
        experiment_name = 'test_gcloud_worker_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=gcloud', '--force-git',
                         '--cloud-timeout=120'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        ):
            pass

    @timeout(500)
    def test_worker_spot(self):
        experiment_name = 'test_gcloud_spot_worker_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=gcspot', '--force-git',
                         '--cloud-timeout=120'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        ):
            pass


@unittest.skipIf(
    not has_aws_credentials(),
    'boto3 not present, won\'t be able to use AWS API')
class EC2WorkerTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def get_worker_manager(self):
        return EC2WorkerManager()

    @timeout(500)
    def test_worker(self):
        experiment_name = 'test_ec2_worker_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=ec2', '--force-git', '--gpus=1',
                         '--cloud-timeout=120'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        ):
            pass

    @timeout(500)
    def test_worker_spot(self):
        experiment_name = 'test_ec2_worker_' + str(uuid.uuid4())
        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[
                '--cloud=ec2spot',
                '--force-git',
                '--bid=50%',
                '--cloud-timeout=120',
            ],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        )

    def test_get_ondemand_prices(self):
        wm = self.get_worker_manager()
        prices = wm._get_ondemand_prices(['c4.large', 'p2.xlarge'])

        expected_prices = {'c4.large': 0.1, 'p2.xlarge': 0.9}
        self.assertEquals(prices, expected_prices)


if __name__ == '__main__':
    unittest.main()
