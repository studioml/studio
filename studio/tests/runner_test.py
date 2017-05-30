import unittest
import os
import shutil
import tempfile
import uuid

from studio import fs_tracker
from studio.runner import LocalExecutor


class RunnerTest(unittest.TestCase):
    def test_LocalExecutor_run(self):
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)
        executor = LocalExecutor('test_config.yaml')

        test_script = 'tf_hello_world.py'
        experiment_name = 'experimentHelloWorld'
        keybase = "/experiments/" + experiment_name
        executor.run(test_script, ['arg0'], experiment_name=experiment_name)

        # test saved arguments
        saved_args = executor.db[keybase + '/args']
        self.assertTrue(len(saved_args) == 1)
        self.assertTrue(saved_args[0] == 'arg0')
        self.assertTrue(executor.db[keybase + '/filename'] == test_script)

        executor.db._download_modeldir(experiment_name)
        with open(os.path.join(fs_tracker.get_model_directory(experiment_name),
                               'output.log'), 'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], '[ 2.  6.]')

        self.check_workspace(executor.db, keybase + '/workspace')
        self.check_workspace(executor.db, keybase + '/workspace_latest')

    def check_workspace(self, db, keybase):

        tmpdir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        os.mkdir(tmpdir)
        db._download_dir(keybase, tmpdir)

        for _, _, files in os.walk('.', topdown=False):
            for filename in files:
                downloaded_filename = os.path.join(tmpdir, filename)
                with open(downloaded_filename, 'rb') as f1:
                    data1 = f1.read()
                with open(filename, 'rb') as f2:
                    data2 = f2.read()

                self.assertTrue(data1 == data2)

        for _, _, files in os.walk('tmpdir', topdown=False):
            for filename in files:
                downloaded_filename = os.path.join(tmpdir, filename)
                with open(downloaded_filename, 'rb') as f1:
                    data1 = f1.read()
                with open(filename, 'rb') as f2:
                    data2 = f2.read()

                self.assertTrue(data1 == data2)

        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
