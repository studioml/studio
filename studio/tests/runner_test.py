import unittest
import os
import shutil
import tempfile
import uuid
import subprocess

from studio import fs_tracker, model


class RunnerTest(unittest.TestCase):
    def test_runner_local(self):
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)

        experiment_name = 'experimentHelloWorld'
        test_script = 'tf_hello_world.py'
        db = model.get_db_provider(model.get_config('test_config.yaml'))
        db.delete_experiment(experiment_name)

        p = subprocess.Popen(['studio-runner',
                              '--config=test_config.yaml',
                              '--experiment=' + experiment_name,
                              test_script, 'arg0'])

        p.wait()

        # test saved arguments
        keybase = "/experiments/" + experiment_name
        saved_args = db[keybase + '/args']
        self.assertTrue(len(saved_args) == 1)
        self.assertTrue(saved_args[0] == 'arg0')
        self.assertTrue(db[keybase + '/filename'] == test_script)

        db._download_modeldir(experiment_name)
        with open(os.path.join(fs_tracker.get_model_directory(experiment_name),
                               'output.log'), 'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], '[ 2.  6.]')

        self.check_workspace(db, keybase + '/workspace.tgz')

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_runner_remote(self):
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)

        experiment_name = 'experimentHelloWorld'
        test_script = 'tf_hello_world.py'
        queue_name = 'test_queue'
        db = model.get_db_provider(model.get_config('test_config.yaml'))
        db.delete_experiment(experiment_name)

        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"])

        p = subprocess.Popen(['studio-runner',
                              '--config=test_config.yaml',
                              '--experiment=' + experiment_name,
                              '--queue=' + queue_name,
                              test_script, 'arg0'])

        p.wait()
        pw.wait()

        # test saved arguments
        keybase = "/experiments/" + experiment_name
        saved_args = db[keybase + '/args']
        self.assertTrue(len(saved_args) == 1)
        self.assertTrue(saved_args[0] == 'arg0')
        self.assertTrue(db[keybase + '/filename'] == test_script)

        db._download_modeldir(experiment_name)
        with open(os.path.join(fs_tracker.get_model_directory(experiment_name),
                               'output.log'), 'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], '[ 2.  6.]')

        self.check_workspace(db, keybase + '/workspace.tgz')

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
