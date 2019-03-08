import unittest
import os
import tempfile
import uuid
import subprocess

from studio.pubsub_queue import PubsubQueue
from studio import logs
from local_worker_test import stubtest_worker

from timeout_decorator import timeout
from env_detect import on_gcp


@unittest.skip('testing requires docker')
class RemoteWorkerTest(unittest.TestCase):
    _multiprocess_shared_ = True

    @timeout(590)
    @unittest.skipIf(
        not on_gcp(),
        'User indicated not on gcp')
    class UserIndicatedOnGCPTest(unittest.TestCase):
        def test_on_enviornment(self):
            self.assertTrue(
                'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys())

    @unittest.skipIf(
        (not on_gcp()) or
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Skipping due to userinput or GCP Not detected' +
        'variable not set, won'
        ' be able to use google ' +
        'PubSub')
    def test_remote_worker(self):
        experiment_name = 'test_remote_worker_' + str(uuid.uuid4())
        queue_name = experiment_name
        logger = logs.getLogger('test_remote_worker')
        logger.setLevel(10)

        pw = subprocess.Popen(
            ['studio-start-remote-worker',
             '--queue=' + queue_name,
             '--single-run',
             '--no-cache',
             '--timeout=30',
             '--image=peterzhokhoff/studioml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--queue=' + queue_name, '--force-git'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.0 6.0 ]',
            queue=PubsubQueue(queue_name))

        workerout, _ = pw.communicate()
        if workerout:
            logger.debug("studio-start-remote-worker output: \n" +
                         str(workerout))

    @timeout(590)
    @unittest.skipIf(
        (not on_gcp()) or
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Skipping due to userinput or GCP Not detected' +
        'variable not set, won'
        ' be able to use google ' +
        'PubSub')
    def test_remote_worker_c(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        logger = logs.getLogger('test_remote_worker_c')
        logger.setLevel(10)
        experiment_name = "test_remote_worker_c_" + str(uuid.uuid4())

        random_str1 = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())

        queue_name = experiment_name
        pw = subprocess.Popen(
            ['studio-start-remote-worker',
             '--queue=' + queue_name,
             '--single-run',
             '--no-cache',
             '--image=peterzhokhoff/studioml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        db = stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[
                '--capture=' + tmpfile + ':f',
                '--queue=' + queue_name,
                '--force-git'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1,
            queue=PubsubQueue(queue_name),
            delete_when_done=False)

        workerout, _ = pw.communicate()
        if workerout:
            logger.debug("studio-start-remote-worker output: \n" +
                         str(workerout))
        os.remove(tmpfile)

        tmppath = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        if os.path.exists(tmppath):
            os.remove(tmppath)

        db.get_artifact(
            db.get_experiment(experiment_name).artifacts['f'],
            tmppath,
            only_newer=False
        )

        with open(tmppath, 'r') as f:
            self.assertEquals(f.read(), random_str2)
        os.remove(tmppath)
        db.delete_experiment(experiment_name)

    @timeout(590)
    @unittest.skipIf(
        (not on_gcp()) or
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Skipping due to userinput or GCP Not detected' +
        'variable not set, won'
        ' be able to use google ' +
        'PubSub')
    def test_remote_worker_co(self):
        logger = logs.getLogger('test_remote_worker_co')
        logger.setLevel(10)

        tmpfile = os.path.join(tempfile.gettempdir(),
                               str(uuid.uuid4()))

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        experiment_name = 'test_remote_worker_co_' + str(uuid.uuid4())
        queue_name = experiment_name
        pw = subprocess.Popen(
            ['studio-start-remote-worker',
             '--queue=' + queue_name,
             '--single-run',
             '--no-cache',
             '--image=peterzhokhoff/studioml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[
                '--capture-once=' + tmpfile + ':f',
                '--queue=' + queue_name,
                '--force-git'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str,
            queue=PubsubQueue(queue_name))

        workerout, _ = pw.communicate()
        logger.debug('studio-start-remote-worker output: \n' + str(workerout))

        os.remove(tmpfile)

    @timeout(590)
    @unittest.skipIf(
        (not on_gcp()) or
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Skipping due to userinput or GCP Not detected' +
        'variable not set, won'
        ' be able to use google ' +
        'PubSub')
    def test_baked_image(self):

        # create a docker image with baked in credentials
        # and run a remote worker tests with it
        logger = logs.getLogger('test_baked_image')
        logger.setLevel(logs.DEBUG)

        # check if docker is installed
        dockertestp = subprocess.Popen(['docker'],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)

        dockertestout, _ = dockertestp.communicate()
        if dockertestout:
            logger.info("docker test output: \n" + str(dockertestout))

        if dockertestp.returncode != 0:
            logger.error("docker is not installed (correctly)")
            return

        image = 'test_image' + str(uuid.uuid4())

        addcredsp = subprocess.Popen(
            [
                'studio-add-credentials',
                '--tag=' + image,
                '--base-image=peterzhokhoff/studioml'],
            # stdout=subprocess.PIPE,
            # stderr=subprocess.STDOUT
        )

        addcredsout, _ = addcredsp.communicate()
        if addcredsout:
            logger.info('studio-add-credentials output: \n' + str(addcredsout))
        if addcredsp.returncode != 0:
            logger.error("studio-add-credentials failed.")
            self.assertTrue(False)

        experiment_name = 'test_remote_worker_baked' + str(uuid.uuid4())
        queue_name = experiment_name
        logger = logs.getLogger('test_baked_image')
        logger.setLevel(10)

        pw = subprocess.Popen(
            ['studio-start-remote-worker',
             '--queue=' + queue_name,
             '--no-cache',
             '--single-run',
             '--timeout=30',
             '--image=' + image],
            # stdout=subprocess.PIPE,
            # stderr=subprocess.STDOUT
        )

        stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--queue=' + queue_name, '--force-git'],
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            script_args=['arg0'],
            expected_output='[ 2.0 6.0 ]',
            queue=PubsubQueue(queue_name))

        workerout, _ = pw.communicate()
        if workerout:
            logger.debug(
                "studio-start-remote-worker output: \n" +
                str(workerout))

        rmip = subprocess.Popen(['docker', 'rmi', image],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

        rmiout, _ = rmip.communicate()

        if rmiout:
            logger.info('docker rmi output: \n' + str(rmiout))


if __name__ == "__main__":
    unittest.main()
