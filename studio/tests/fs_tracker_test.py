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
                '.tfstudio/models/testExperiment'))

    def test_get_model_directory_noargs(self):
        testPath = 'testPath'
        os.environ['TFSTUDIO_MODEL_PATH'] = testPath
        self.assertTrue(testPath == fs_tracker.get_model_directory())

    def test_set_model_directory(self):
        experimentName = 'testExperiment'
        env = {}
        fs_tracker.setup_model_directory(env, experimentName)

        expectedPath = os.path.join(
            os.path.expanduser('~'),
            '.tfstudio/models/testExperiment')
        self.assertTrue(expectedPath == env['TFSTUDIO_MODEL_PATH'])
        self.assertTrue(os.path.isdir(expectedPath))


if __name__ == "__main__":
    unittest.main()
