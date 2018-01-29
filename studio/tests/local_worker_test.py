import unittest
import os
import shutil
import tempfile
import uuid
import subprocess
import time
from timeout_decorator import timeout
import traceback
import numpy as np

try:
    import keras
except BaseException:
    keras = None

from studio import model, logs
from studio.local_queue import LocalQueue, get_local_queue_lock
from studio.util import has_aws_credentials, sixdecode, retry

TEST_TIMEOUT = 600


class LocalWorkerTest(unittest.TestCase):

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_runner_local(self):
        with stubtest_worker(
            self,
            experiment_name='test_runner_local_' + str(uuid.uuid4()),
            config_name='test_config_http_client.yaml',
            test_script='tf_hello_world.py',
            runner_args=[],
            script_args=['arg0'],
            expected_output='[ 2.0 6.0 ]'
        ):
            pass

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_args_conflict(self):
        with stubtest_worker(
            self,
            experiment_name='test_runner_conflict_' + str(uuid.uuid4()),
            config_name='test_config.yaml',
            runner_args=[],
            test_script='conflicting_args.py',
            script_args=['--experiment', 'aaa'],
            expected_output='Experiment key = aaa'
        ):
            pass

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_local_hyperparam(self):
        with stubtest_worker(
            self,
            experiment_name='test_local_hyperparam' + str(uuid.uuid4()),
            runner_args=['--verbose=debug'],
            config_name='test_config_http_client.yaml',
            test_script='hyperparam_hello_world.py',
            expected_output='0.3'
        ):
            pass

        with stubtest_worker(
            self,
            experiment_name='test_local_hyperparam' + str(uuid.uuid4()),
            runner_args=[
                '--verbose=debug',
                '--hyperparam=learning_rate=0.4'
            ],
            config_name='test_config_http_client.yaml',
            test_script='hyperparam_hello_world.py',
            expected_output='0.4'
        ):
            pass

    @unittest.skip('peterz figure out the failure - happens intermittently ' +
                   'when running in parallel')
    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_local_worker_ce(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile_ce_' +
                               str(uuid.uuid4()) + '.txt')

        random_str1 = str(uuid.uuid4())

        with open(tmpfile, 'w') as f:
            f.write(random_str1)

        random_str2 = str(uuid.uuid4())
        experiment_name = 'test_local_worker_c' + str(uuid.uuid4())
        print("random_str1 = " + random_str1)
        print("random_str2 = " + random_str2)
        print("experiment_name = " + experiment_name)
        print("tmpfile = " + tmpfile)

        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=['--capture=' + tmpfile + ':f',
                         '--verbose=debug'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[random_str2],
            expected_output=random_str1,
            delete_when_done=False
        ) as db:
            pass

        tmppath = db.get_artifact(
            db.get_experiment(experiment_name).artifacts['f']
        )

        with open(tmppath, 'r') as f:
            self.assertTrue(f.read() == random_str2)
        os.remove(tmppath)

        with stubtest_worker(
            self,
            experiment_name='test_local_worker_e' + str(uuid.uuid4()),
            runner_args=['--reuse={}/f:f'.format(experiment_name)],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str2
        ) as db:

            db.delete_experiment(experiment_name)

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_local_worker_co(self):
        tmpfile = os.path.join(tempfile.gettempdir(),
                               'tmpfile' +
                               str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmpfile, 'w') as f:
            f.write(random_str)

        # with get_local_queue_lock():
        with stubtest_worker(
            self,
            experiment_name='test_local_worker_co' + str(uuid.uuid4()),
            runner_args=['--capture-once=' + tmpfile + ':f'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=random_str
        ):
            pass

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_local_worker_co_url(self):
        expected_str = 'Zabil zaryad ya v pushku tugo'
        url = 'https://storage.googleapis.com/studio-ed756.appspot.com/' + \
              'tests/url_artifact.txt'

        # with get_local_queue_lock():
        with stubtest_worker(
            self,
            experiment_name='test_local_worker_co_url' + str(uuid.uuid4()),
            runner_args=['--capture-once=' + url + ':f'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=expected_str
        ):
            pass

    @unittest.skipIf(
        not has_aws_credentials(),
        'AWS credentials not found, cannot download s3://-like links')
    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_local_worker_co_s3(self):
        expected_str = 'No4 ulica fonar apteka, bessmyslennyj i tusklyj svet'
        s3loc = 's3://studioml-artifacts/tests/download_test/download_test.txt'

        # with get_local_queue_lock():
        with stubtest_worker(
            self,
            experiment_name='test_local_worker_co_s3' + str(uuid.uuid4()),
            runner_args=['--capture-once=' + s3loc + ':f'],
            config_name='test_config_http_client.yaml',
            test_script='art_hello_world.py',
            script_args=[],
            expected_output=expected_str
        ):
            pass

    @unittest.skipIf(keras is None,
                     'keras is required for this test')
    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_save_get_model(self):
        experiment_name = 'test_save_get_model' + str(uuid.uuid4())
        # with get_local_queue_lock():
        with stubtest_worker(
            self,
            experiment_name=experiment_name,
            runner_args=[],
            config_name='test_config_http_client.yaml',
            test_script='save_model.py',
            script_args=[],
            expected_output='',
            delete_when_done=False,
            test_output=False
        ) as db:

            experiment = db.get_experiment(experiment_name)
            saved_model = experiment.get_model(db)

            v = np.random.rand(1, 2)
            prediction = saved_model.predict(v)
            expected = v * 2

            self.assertTrue(np.isclose(prediction, expected).all())

            db.delete_experiment(experiment)

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_stop_experiment(self):
        my_path = os.path.dirname(os.path.realpath(__file__))

        logger = logs.getLogger('test_stop_experiment')
        logger.setLevel(10)

        config_name = os.path.join(my_path, 'test_config_http_client.yaml')
        key = 'test_stop_experiment' + str(uuid.uuid4())

        with model.get_db_provider(model.get_config(config_name)) as db:
            try:
                db.delete_experiment(key)
            except Exception:
                pass

            p = subprocess.Popen(['studio', 'run',
                                  '--config=' + config_name,
                                  '--experiment=' + key,
                                  '--force-git',
                                  '--verbose=debug',
                                  'stop_experiment.py'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 cwd=my_path)

            # wait till experiment spins up
            experiment = None
            while experiment is None or experiment.status == 'waiting':
                time.sleep(1)
                try:
                    experiment = db.get_experiment(key)
                except BaseException:
                    pass

            logger.info('Stopping experiment')
            db.stop_experiment(key)
            pout, _ = p.communicate()

            if pout:
                logger.debug("studio run output: \n" + pout.decode())

            db.delete_experiment(key)

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_experiment_maxduration(self):
        my_path = os.path.dirname(os.path.realpath(__file__))

        logger = logs.getLogger('test_experiment_maxduration')
        logger.setLevel(10)

        config_name = os.path.join(my_path, 'test_config_http_client.yaml')
        key = 'test_experiment_maxduration' + str(uuid.uuid4())

        with model.get_db_provider(model.get_config(config_name)) as db:
            try:
                db.delete_experiment(key)
            except Exception:
                pass

            p = subprocess.Popen(['studio', 'run',
                                  '--config=' + config_name,
                                  '--experiment=' + key,
                                  '--force-git',
                                  '--verbose=debug',
                                  '--max-duration=10s',
                                  'stop_experiment.py'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 cwd=my_path)

            pout, _ = p.communicate()
            if pout:
                logger.debug("studio run output: \n" + pout.decode())

            db.delete_experiment(key)

    @timeout(TEST_TIMEOUT, use_signals=False)
    def test_experiment_lifetime(self):
        my_path = os.path.dirname(os.path.realpath(__file__))

        logger = logs.getLogger('test_experiment_lifetime')
        logger.setLevel(10)

        config_name = os.path.join(my_path, 'test_config_http_client.yaml')
        key = 'test_experiment_lifetime' + str(uuid.uuid4())

        with model.get_db_provider(model.get_config(config_name)) as db:
            try:
                db.delete_experiment(key)
            except Exception:
                pass

            p = subprocess.Popen(['studio', 'run',
                                  '--config=' + config_name,
                                  '--experiment=' + key,
                                  '--force-git',
                                  '--verbose=debug',
                                  '--lifetime=-10m',
                                  'stop_experiment.py'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 cwd=my_path)

            pout, _ = p.communicate()

            if pout:
                logger.debug("studio run output: \n" + pout.decode())

            db.delete_experiment(key)


def stubtest_worker(
        testclass,
        experiment_name,
        runner_args,
        config_name,
        test_script,
        expected_output,
        script_args=[],
        queue=LocalQueue(),
        wait_for_experiment=True,
        delete_when_done=True,
        test_output=True,
        test_workspace=True):

    my_path = os.path.dirname(os.path.realpath(__file__))
    config_name = os.path.join(my_path, config_name)
    logger = logs.getLogger('stubtest_worker')
    logger.setLevel(10)

    queue.clean()

    with model.get_db_provider(model.get_config(config_name)) as db:
        try:
            db.delete_experiment(experiment_name)
        except Exception:
            pass

    os.environ['PYTHONUNBUFFERED'] = 'True'
    p = subprocess.Popen(['studio', 'run'] + runner_args +
                         ['--config=' + config_name,
                          '--verbose=debug',
                          '--force-git',
                          '--experiment=' + experiment_name,
                          test_script] + script_args,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         close_fds=True,
                         cwd=my_path)

    pout, _ = p.communicate()

    if pout:
        logger.debug("studio run output: \n" + sixdecode(pout))
        splitpout = sixdecode(pout).split('\n')
        experiments = [line.split(' ')[-1] for line in splitpout
                       if line.startswith('studio run: submitted experiment')]
        logger.debug("added experiments: {}".format(experiments))

    db = model.get_db_provider(model.get_config(config_name))
    experiment_name = experiments[0]

    try:
        experiment = db.get_experiment(experiment_name)
        if wait_for_experiment:
            while not experiment or not experiment.status == 'finished':
                experiment = db.get_experiment(experiment_name)

        if test_output:
            with open(db.get_artifact(experiment.artifacts['output']),
                      'r') as f:
                data = f.read()
                split_data = data.strip().split('\n')
                print(data)
                testclass.assertEquals(split_data[-1], expected_output)

        if test_workspace:
            check_workspace(testclass, db, experiment_name)

        if delete_when_done:
            retry(lambda: db.delete_experiment(experiment_name), sleep_time=10)

        return db

    except Exception as e:
        print("Exception {} raised during test".format(e))
        print("worker output: \n {}".format(pout))
        print("Exception trace:")
        print(traceback.format_exc())
        raise e


def check_workspace(testclass, db, key):

    tmpdir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
    os.mkdir(tmpdir)
    experiment = retry(lambda: db.get_experiment(key), sleep_time=5)
    artifact = experiment.artifacts['workspace']
    localpath = retry(
        lambda: db.get_artifact(
            artifact,
            tmpdir,
            only_newer=False),
        sleep_time=5)

    for _, _, files in os.walk(localpath, topdown=False):
        for filename in files:
            downloaded_filename = os.path.join(tmpdir, filename)
            if downloaded_filename.endswith('.pyc'):
                continue

            with open(downloaded_filename, 'rb') as f1:
                data1 = f1.read()
            with open(os.path.join(db.get_artifact(artifact), filename),
                      'rb') as f2:
                data2 = f2.read()

            testclass.assertTrue(
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

            testclass.assertTrue(data1 == data2)

    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
