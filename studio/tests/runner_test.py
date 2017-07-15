import unittest
import numpy as np
import uuid
from timeout_decorator import timeout

from studio import runner
from local_worker_test import stubtest_worker


class RunnerTest(unittest.TestCase):

    def test_parse_range(self):
        self.assertTrue(np.isclose(runner.parse_range('1,2,3'),
                                   [1.0, 2.0, 3.0]).any())

        self.assertTrue(np.isclose(runner.parse_range(':5'),
                                   [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]).any())

        self.assertTrue(np.isclose(runner.parse_range('2:5'),
                                   [2.0, 3.0, 4.0, 5.0]).any())

        self.assertTrue(np.isclose(runner.parse_range('0.1:0.05:0.3'),
                                   [0.1, 0.15, 0.2, 0.25, 0.3]).any())

        self.assertTrue(np.isclose(runner.parse_range('0.1:3:0.3'),
                                   [0.1, 0.2, 0.3]).any())

        self.assertTrue(np.isclose(runner.parse_range('0.01:4l:10'),
                                   [0.01, 0.1, 1, 10]).any())

    def test_unfold_tuples(self):
        test_dict = {'a': [1, 2, 3], 'b': [4, 5]}

        expected_tuples = [
            {'a': 1, 'b': 4}, {'a': 2, 'b': 4}, {'a': 3, 'b': 4},
            {'a': 1, 'b': 5}, {'a': 2, 'b': 5}, {'a': 3, 'b': 5}]

        self.assertTrue(runner.unfold_tuples(test_dict) == expected_tuples)

    @timeout(30)
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
        list2 = ['keras==1.0.9', 'h5py==2.7.0']

        result = set(runner.add_packages(list1, list2))
        expected_result = set([
            'boto3==1.1.3', 'h5py==2.7.0', 'keras==1.0.9'])

        self.assertEquals(result, expected_result)


if __name__ == '__main__':
    unittest.main()
