import unittest
import numpy as np

from studio.hyperparameter import HyperparameterParser, Hyperparameter
from studio import logs


class RunnerArgs(object):
    def __init__(self):
        self.optimizer = "grid"
        self.verbose = False


class HyperparamTest(unittest.TestCase):
    def test_parse_range(self):
        logger = logs.get_logger('test_stop_experiment')
        h = HyperparameterParser(RunnerArgs(), logger)
        range_strs = ['1,2,3', ':5', '2:5', '0.1:0.05:0.3', '0.1:3:0.3',
                      '0.01:4l:10']
        gd_truths = [
            [
                1.0, 2.0, 3.0], [
                0.0, 1.0, 2.0, 3.0, 4.0, 5.0], [
                2.0, 3.0, 4.0, 5.0], [
                    0.1, 0.15, 0.2, 0.25, 0.3], [
                        0.1, 0.2, 0.3], [
                            0.01, 0.1, 1, 10]]

        for range_str, gd_truth in zip(range_strs, gd_truths):
            hyperparameter = h._parse_grid("test", range_str)
            self.assertTrue(np.isclose(hyperparameter.values, gd_truth).all())

    def test_unfold_tuples(self):
        logger = logs.get_logger('test_stop_experiment')
        h = HyperparameterParser(RunnerArgs(), logger)

        hyperparams = [Hyperparameter(name='a', values=[1, 2, 3]),
                       Hyperparameter(name='b', values=[4, 5])]

        expected_tuples = [
            {'a': 1, 'b': 4}, {'a': 2, 'b': 4}, {'a': 3, 'b': 4},
            {'a': 1, 'b': 5}, {'a': 2, 'b': 5}, {'a': 3, 'b': 5}]

        self.assertEqual(
            sorted(h.convert_to_tuples(hyperparams), key=lambda x: str(x)),
            sorted(expected_tuples, key=lambda x: str(x)))


if __name__ == '__main__':
    unittest.main()
