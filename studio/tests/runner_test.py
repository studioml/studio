import unittest
import os
import shutil
import tempfile
import uuid
import subprocess

from studio import fs_tracker, model
from studio.pubsub_queue import PubsubQueue


class RunnerTest(unittest.TestCase):
    def test_runner_local(self):
        self.stub_runner_local(
            experiment_name='test_runner_local',
            runner_args=[],
            config_name='test_config.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]'
        )

    def test_runner_local_art(self):

        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())
        experiment_name = 'test_runner_local_art' + str(uuid.uuid4())

        self.stub_runner_local(
            experiment_name=experiment_name,
            runner_args=['--art=' + tmpfile + ':f'],
            config_name='test_config.yaml',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1
        )

        db = model.get_db_provider(model.get_config('test_config.yaml'))
        tmppath = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        db._download_dir(tmppath, 'experiments/{}/f.tgz'.format(experiment_name))
        with open(tmppath, 'r') as f:
            self.assertTrue(f.read() == random_str2)
        os.remove(tmppath)

        self.stub_runner_local(
            experiment_name='test_runner_local_arte',
            runner_args=['--arte={}/f:f'.format(experiment_name)],
            config_name='test_config.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str2
        )

        db.delete_experiment(experiment_name)

    def test_runner_local_arti(self):

        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        self.stub_runner_local(
            experiment_name='test_runner_local_arti',
            runner_args=['--arti=' + tmpfile + ':f'],
            config_name='test_config.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str
        )

    def stub_runner_local(
            self,
            experiment_name,
            runner_args,
            config_name,
            test_script,
            script_args,
            expected_output):
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)

        if os.path.exists(fs_tracker.get_queue_directory()):
            shutil.rmtree(fs_tracker.get_queue_directory())

        db = model.get_db_provider(model.get_config(config_name))
        try:
            db.delete_experiment(experiment_name)
        except Exception:
            pass

        p = subprocess.Popen(['studio-runner'] + runner_args +
                             ['--config=' + config_name,
                              '--experiment=' + experiment_name,
                              test_script] + script_args)

        p.wait()

        # test saved arguments
        keybase = "/experiments/" + experiment_name
        saved_args = db[keybase + '/args']
        if saved_args is not None:
            self.assertTrue(len(saved_args) == len(script_args))
            for i in range(len(saved_args)):
                self.assertTrue(saved_args[i] == script_args[i])
            self.assertTrue(db[keybase + '/filename'] == test_script)
        else:
            self.assertTrue(script_args is None or len(script_args) == 0)

        experiment = db.get_experiment(experiment_name)
        db._download_modeldir(experiment_name)
        db._download_dir(
                fs_tracker.get_artifact_cache("output", experiment_name), 
                experiment.artifacts["output"]["key"]
        )

        with open(fs_tracker.get_artifact_cache("output", experiment_name),
                  'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], expected_output)

        self.check_workspace(db, keybase + '/workspace.tgz')

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_runner_remote(self):
        self.stub_runner_remote(
            experiment_name='test_runner_remote',
            runner_args=[],
            config_name='test_config.yaml',
            queue_name='test_runner_remote',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]')

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_runner_remote_art(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())

        self.stub_runner_remote(
            experiment_name='test_runner_remote_art',
            runner_args=['--art=' + tmpfile + ':f'],
            config_name='test_config.yaml',
            queue_name='test_runner_remote',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1
        )

        db = model.get_db_provider(model.get_config('test_config.yaml'))
        tmppath = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        db._download_dir(tmppath, 'experiments/test_runner_remote_art/f.tgz')
        with open(tmppath, 'r') as f:
            self.assertTrue(f.read() == random_str2)
        os.remove(tmppath)

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_runner_remote_arti(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        self.stub_runner_remote(
            experiment_name='test_runner_remote_arti',
            runner_args=['--arti=' + tmpfile + ':f'],
            config_name='test_config.yaml',
            queue_name='test_runner_remote',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str
        )

    def stub_runner_remote(
            self,
            experiment_name,
            runner_args,
            config_name,
            queue_name,
            test_script,
            script_args,
            expected_output):
        my_path = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_path)


        PubsubQueue(queue_name).clean()

        db = model.get_db_provider(model.get_config(config_name))

        try:
            db.delete_experiment(experiment_name)
        except BaseException:
            pass

        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"])

        p = subprocess.Popen(['studio-runner',
                              '--config=' + config_name,
                              '--experiment=' + experiment_name,
                              '--queue=' + queue_name] +
                             runner_args +
                             [test_script] +
                             script_args)

        p.wait()
        pw.wait()

        # test saved arguments
        keybase = "/experiments/" + experiment_name
        saved_args = db[keybase + '/args']
        if saved_args is not None:
            self.assertTrue(len(saved_args) == len(script_args))
            for i in range(len(saved_args)):
                self.assertTrue(saved_args[i] == script_args[i])
            self.assertTrue(db[keybase + '/filename'] == test_script)
        else:
            self.assertTrue(script_args is None or len(script_args) == 0)

        self.assertTrue(db[keybase + '/filename'] == test_script)

        experiment = db.get_experiment(experiment_name)
        db._download_modeldir(experiment_name)
        db._download_dir(
                fs_tracker.get_artifact_cache("output", experiment_name), 
                experiment.artifacts["output"]["key"]
        )

        with open(fs_tracker.get_artifact_cache("output", experiment_name),
                  'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], expected_output)

        self.check_workspace(db, keybase + '/workspace.tgz')

    def check_workspace(self, db, key):

        tmpdir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        os.mkdir(tmpdir)
        db._download_dir(tmpdir, key)

        for _, _, files in os.walk('.', topdown=False):
            for filename in files:
                downloaded_filename = os.path.join(tmpdir, filename)
                with open(downloaded_filename, 'rb') as f1:
                    data1 = f1.read()
                with open(filename, 'rb') as f2:
                    data2 = f2.read()

                self.assertTrue(
                    data1 == data2,
                    ('File comparison between local {} ' +
                     'and downloaded {} has failed')
                    .format(
                        filename,
                        downloaded_filename))

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
