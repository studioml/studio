import unittest

from studio import model


class RunnerTest(unittest.TestCase):

    def test_add_packages(self):

        list1 = ['keras==2.0.5', 'boto3==1.1.3']
        list2 = ['keras==1.0.9', 'h5py==2.7.0', 'abc']

        result = set(model.add_packages(list1, list2))
        expected_result = set(['boto3==1.1.3', 'h5py==2.7.0',
                               'keras==1.0.9', 'abc'])

        self.assertEquals(result, expected_result)


if __name__ == '__main__':
    unittest.main()
