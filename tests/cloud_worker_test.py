import unittest
import os
import uuid

from studio.gcloud_worker import GCloudWorkerManager
from studio.ec2cloud_worker import EC2WorkerManager
from local_worker_test import stubtest_worker

from timeout_decorator import timeout
from studio.util import has_aws_credentials
from env_detect import on_gcp, on_aws

#900
CLOUD_TEST_TIMEOUT = 60


@unittest.skipIf(
    not on_gcp(),
    'User indicated not on gcp')
class UserIndicatedOnGCPTest(unittest.TestCase):
    def test_on_enviornment(self):
        self.assertTrue('GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys())


@unittest.skipIf(
    (not on_gcp()) or
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'Skipping due to userinput or GCP Not detected')
class GCloudWorkerTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def get_worker_manager(self):
        project = 'studio-ed756'
        return GCloudWorkerManager(project)

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
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
            expected_output='[ 2.0 6.0 ]',
        ):
            pass

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
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
            expected_output='[ 2.0 6.0 ]',
        ):
            pass

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_worker_spot_container(self):
        experiment_name = 'test_gcloud_spot_simg_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=gcspot',
                         '--force-git',
                         '--cloud-timeout=120',
                         '--container=shub://vsoch/hello-world'],

            config_name='test_config_http_client.yaml',
            test_script='',
            script_args=[],
            expected_output='RaawwWWWWWRRRR!!',
            test_workspace=False
        ):
            pass


@unittest.skipIf(
    not on_aws(),
    'User indicated not on aws')
class UserIndicatedOnAWSTest(unittest.TestCase):
    def test_on_enviornment(self):
        self.assertTrue(has_aws_credentials())


@unittest.skipIf(
    (not on_aws()) or not has_aws_credentials(),
    'Skipping due to userinput or AWS Not detected')
class EC2WorkerTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def get_worker_manager(self):
        return EC2WorkerManager()

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_worker(self):
        experiment_name = 'test_ec2_worker_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=ec2', '--force-git', '--gpus=1',
                         '--cloud-timeout=120', '--ssh-keypair=peterz-k1'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.0 6.0 ]',
        ):
            pass

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
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
            expected_output='[ 2.0 6.0 ]',
        )

    def test_get_ondemand_prices(self):
        wm = self.get_worker_manager()
        prices = wm._get_ondemand_prices(['c4.large', 'p2.xlarge'])

        expected_prices = {'c4.large': 0.1, 'p2.xlarge': 0.9}
        self.assertEquals(prices, expected_prices)

    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_worker_spot_container(self):
        experiment_name = 'test_gcloud_spot_simg_' + str(uuid.uuid4())
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=ec2spot',
                         '--force-git',
                         '--cloud-timeout=120',
                         '--container=shub://vsoch/hello-world'],

            config_name='test_config_http_client.yaml',
            test_script='',
            script_args=[],
            expected_output='RaawwWWWWWRRRR!!',
            test_workspace=False
        ):
            pass


if __name__ == '__main__':
    unittest.main()
