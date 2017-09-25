import unittest
import uuid
from timeout_decorator import timeout

from studio import runner
from local_worker_test import stubtest_worker


class RunnerTest(unittest.TestCase):

    @timeout(90)
    def test_args_conflict(self):
        stubtest_worker(
            self,
            experiment_name='test_runner_conflict_' + str(uuid.uuid4()),
            runner_args=['--verbose=debug'],
            config_name='test_config.yaml',
            test_script='conflicting_args.py',
            script_args=['--experiment', 'aaa'],
            expected_output='Experiment key = aaa'
        )

    def test_add_packages(self):

        list1 = ['keras==2.0.5', 'boto3==1.1.3']
        list2 = ['keras==1.0.9', 'h5py==2.7.0', 'abc']

        result = set(runner.add_packages(list1, list2))
        expected_result = set(['boto3==1.1.3', 'h5py==2.7.0',
                               'keras==1.0.9', 'abc'])

        self.assertEquals(result, expected_result)


if __name__ == '__main__':
    unittest.main()
