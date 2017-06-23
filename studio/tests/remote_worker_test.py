import unittest
import os
import tempfile
import uuid
import subprocess

from studio import fs_tracker, model
from studio.pubsub_queue import PubsubQueue
from local_worker_test import check_workspace


class RunnerTest(unittest.TestCase):

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
    def test_runner_remote_c(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        experiment_name = "test_runner_remote_c"
        db = model.get_db_provider(model.get_config('test_config.yaml'))

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())

        self.stub_runner_remote(
            experiment_name=experiment_name, 
            runner_args=['--capture=' + tmpfile + ':f'],
            config_name='test_config.yaml',
            queue_name='test_runner_remote',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1
        )

        tmppath = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        db.store.get_artifact(
                {'key':'experiments/test_runner_remote_c/f.tgz'},
                tmppath,
                only_newer=False
            )

        with open(tmppath, 'r') as f:
            self.assertTrue(f.read() == random_str2)
        os.remove(tmppath)


    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_runner_remote_co(self):
        return
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile.txt')

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        self.stub_runner_remote(
            experiment_name='test_runner_remote_co',
            runner_args=['--capture-once=' + tmpfile + ':f'],
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
        output_path = db.store.get_artifact(experiment.artifacts['output'])

        with open(output_path, 'r') as f:
            data = f.read()
            split_data = data.strip().split('\n')
            self.assertEquals(split_data[-1], expected_output)

        check_workspace(self, db, experiment_name)


if __name__ == "__main__":
    unittest.main()
