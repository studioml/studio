import unittest
import numpy as np

from studio import runner


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


if __name__ == '__main__':
    unittest.main()
