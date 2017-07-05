import unittest
import os
import tempfile
import uuid
import subprocess

from studio import model
from studio.pubsub_queue import PubsubQueue
from local_worker_test import stubtest_worker


class RemoteWorkerTest(unittest.TestCase):
    _multiprocess_can_split_ = True

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker(self):
        experiment_name = 'test_remote_worker_' + str(uuid.uuid4())
        queue_name = experiment_name
        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"])

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--queue=' + queue_name, '--force-git'],
            config_name='test_config.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
            queue=PubsubQueue(queue_name))

        pw.wait()
        model.get_db_provider(
                model.get_config('test_config.yaml')).delete_experiment(experiment_name)

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker_c(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        experiment_name = "test_remote_worker_c_" + str(uuid.uuid4())
        db = model.get_db_provider(model.get_config('test_config.yaml'))

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())

        queue_name = experiment_name
        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"])

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[
                '--capture=' + tmpfile + ':f',
                '--queue=' + queue_name,
                '--force-git'],
            config_name='test_config.yaml',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1,
            queue=PubsubQueue(queue_name))

        pw.wait()
        os.remove(tmpfile)

        tmppath = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        if os.path.exists(tmppath):
            os.remove(tmppath)

        db.store.get_artifact(
            db.get_experiment(experiment_name).artifacts['f'],
            tmppath,
            only_newer=False
        )

        with open(tmppath, 'r') as f:
            self.assertTrue(f.read() == random_str2)
        os.remove(tmppath)

        model.get_db_provider(
            model.get_config('test_config.yaml')).delete_experiment(experiment_name)

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker_co(self):
        return
        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)
        
        experiment_name = 'test_remote_worker_co_' + str(uuid.uuid4())
        queue_name = experiment_name
        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"])

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[
                '--capture-once=' + tmpfile + ':f',
                '--queue=' + queue_name,
                '--force-git'],
            config_name='test_config.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str,
            queue=PubsubQueue(queue_name))

        pw.wait()
        os.remove(tmpfile)
        model.get_db_provider(
            model.get_config('test_config.yaml')).delete_experiment(experiment_name)



if __name__ == "__main__":
    unittest.main()
