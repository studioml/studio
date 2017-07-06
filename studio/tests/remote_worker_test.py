import unittest
import os
import tempfile
import uuid
import subprocess

from studio.pubsub_queue import PubsubQueue
from local_worker_test import stubtest_worker

from timeout_decorator import timeout
import logging

logging.basicConfig()


class RemoteWorkerTest(unittest.TestCase):
    _multiprocess_can_split_ = True

    @timeout(90)
    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker(self):
        experiment_name = 'test_remote_worker_' + str(uuid.uuid4())
        queue_name = experiment_name
        logger = logging.getLogger('test_remote_worker')
        logger.setLevel(10)

        pw = subprocess.Popen(
            ['studio-start-remote-worker', queue_name, '1'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--queue=' + queue_name, '--force-git'],
            config_name='test_config.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.  6.]',
            queue=PubsubQueue(queue_name))

        workerout, _ = pw.communicate()
        logger.debug("studio-start-remote-worker output: \n" + workerout)

    @timeout(90)
    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker_c(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        logger = logging.getLogger('test_remote_worker_c')
        logger.setLevel(10)
        experiment_name = "test_remote_worker_c_" + str(uuid.uuid4())

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())

        queue_name = experiment_name
        pw = subprocess.Popen(
            ['studio-start-remote-worker', queue_name, "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        db = stubtest_worker(
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
            queue=PubsubQueue(queue_name),
            delete_when_done=False)

        workerout, _ = pw.communicate()
        logger.debug("studio-start-remote-worker output: \n" + workerout)
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
        db.delete_experiment(experiment_name)

    @timeout(90)
    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in
        os.environ.keys(),
        'GOOGLE_APPLICATION_CREDENTIALS environment ' +
        'variable not set, won'' be able to use google ' +
        'PubSub')
    def test_remote_worker_co(self):
        logger = logging.getLogger('test_remote_worker_co')
        logger.setLevel(10)

        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        experiment_name = 'test_remote_worker_co_' + str(uuid.uuid4())
        queue_name = experiment_name
        pw = subprocess.Popen(['studio-start-remote-worker', queue_name, "1"],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)

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

        workerout, _ = pw.communicate()
        logger.debug('studio-start-remote-worker output: \n' + workerout)

        os.remove(tmpfile)


if __name__ == "__main__":
    unittest.main()
