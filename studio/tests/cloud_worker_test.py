import unittest
import os
import uuid

from studio.gcloud_worker import GCloudWorkerManager
from studio.ec2cloud_worker import EC2WorkerManager
from local_worker_test import stubtest_worker
from studio.model import get_db_provider, get_config


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google cloud')
class GCloudWorkerTest(unittest.TestCase):
    def get_worker_manager(self):
        project = 'studio-ed756'
        return GCloudWorkerManager(project)

    def test_worker(self):
        experiment_name = 'test_gcloud_worker_' + str(uuid.uuid4())
        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=gcloud', '--force-git'],
            config_name='test_config.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        )
        get_db_provider(get_config('test_config.yaml')) \
                .delete_experiment(experiment_name)



@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google cloud')
class EC2WorkerTest(unittest.TestCase):
    def get_worker_manager(self):
        return EC2WorkerManager()

    def test_worker(self):
        experiment_name = 'test_ec2_worker_' + str(uuid.uuid4())
        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--cloud=ec2', '--force-git', '--gpus=0'],
            config_name='test_config.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
        )

        get_db_provider(get_config('test_config.yaml')) \
                .delete_experiment(experiment_name)


if __name__ == '__main__':
    unittest.main()
