import unittest
import os

from studio import fs_tracker


class StudioLoggingTest(unittest.TestCase):

    def test_get_model_directory_args(self):
        experimentName = 'testExperiment'
        modelDir = fs_tracker.get_model_directory(experimentName)
        self.assertTrue(
            modelDir == os.path.join(
                os.path.expanduser('~'),
                '.studioml/experiments/testExperiment/modeldir'))

    def test_get_model_directory_noargs(self):
        testExperiment = 'testExperiment'
        testPath = os.path.join(
            os.path.expanduser('~'),
            '.studioml/experiments',
            testExperiment, 'modeldir')

        os.environ['STUDIOML_EXPERIMENT'] = testExperiment
        self.assertTrue(testPath == fs_tracker.get_model_directory())


if __name__ == "__main__":
    unittest.main()
