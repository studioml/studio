import uuid
import random
import unittest
import os
import hashlib
import six
import tempfile
from timeout_decorator import timeout

from .completion_service import CompletionService

from studio.extra_util import has_aws_credentials
from studio.util.util import rand_string, filehash
from studio.storage.storage_util import download_file

_file_url = 'https://s3-us-west-2.amazonaws.com/ml-enn/' + \
            'deepbilevel_datafiles/' + \
            'mightyai_combined_vocab/mightyai_miscfiles.tar.gz'

_file_s3 = 's3://s3-us-west-2.amazonaws.com/studioml-test/t.txt'

LOCAL_TEST_TIMEOUT = 200
CLOUD_TEST_TIMEOUT = 800


class CompletionServiceTest(unittest.TestCase):

    def _run_test(self,
                  args=None,
                  files={},
                  jobfile=None,
                  expected_results=None,
                  **csargs):

        if not(any(csargs)):
            return

        jobfile = self.get_jobfile(jobfile or 'completion_service_testfunc.py')

        args = args or [0, 1]

        expected_results = expected_results or args
        submission_indices = {}
        n_experiments = len(args)
        experimentId = str(uuid.uuid4())

        with CompletionService(experimentId, **csargs) as cs:
            for i in range(0, n_experiments):
                key = cs.submitTaskWithFiles(jobfile, args[i], files)
                submission_indices[key] = i

            for i in range(0, n_experiments):
                result = cs.getResults(blocking=True)
                self.assertEquals(
                    result[1],
                    expected_results[submission_indices[result[0]]]
                )

    def _run_test_files(self,
                        files,
                        n_experiments=2,
                        **csargs):

        expected_results = [(i, self._get_file_hashes(files))
                            for i in range(n_experiments)]
        args = range(n_experiments)
        self._run_test(
            args=args,
            files=files,
            jobfile='completion_service_testfunc_files.py',
            expected_results=expected_results,
            **csargs
        )

    def _run_test_myfiles(self,
                          n_experiments=2,
                          **csargs):

        mypath = os.path.dirname(os.path.realpath(__file__))

        files_in_workspace = os.listdir(mypath)
        files = {f: os.path.join(mypath, f) for f in files_in_workspace if
                 os.path.isfile(os.path.join(mypath, f))}

        files['url'] = _file_url

        # TODO peterz enable passing aws credentials to google workers
        # if has_aws_credentials():
        #     files['s3'] = _file_s3

        expected_results = [
            (i, self._get_file_hashes(files)) for i in range(n_experiments)
        ]

        args = range(n_experiments)
        self._run_test(
            args=args,
            files=files,
            jobfile='completion_service_testfunc_files.py',
            expected_results=expected_results,
            **csargs
        )

    def _get_file_hashes(self, files):
        retval = {}
        for k, v in six.iteritems(files):
            if '://' in v:
                tmpfilename = os.path.join(
                    tempfile.gettempdir(), rand_string(10))
                download_file(v, tmpfilename)
                retval[k] = filehash(tmpfilename)
                os.remove(tmpfilename)
            else:
                retval[k] = filehash(v)

        return retval

    @unittest.skipIf(not has_aws_credentials(),
                     'AWS credentials needed for this test')
    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_ec2(self):
        self._run_test(
            config=self.get_config_path(),
            cloud_timeout=100,
            cloud='ec2')

    @unittest.skipIf(not has_aws_credentials(),
                     'AWS credentials needed for this test')
    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_ec2spot(self):
        self._run_test_myfiles(
            n_experiments=2,
            config=self.get_config_path(),
            cloud_timeout=100,
            cloud='ec2spot',
        )

    @timeout(LOCAL_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_apiserver(self):
        self._run_test_myfiles(
            n_experiments=2,
            config=self.get_config_path(),
            cloud_timeout=LOCAL_TEST_TIMEOUT
        )

    @unittest.skipIf(True,
                     'Test requires k8s style configurations ' +
                     'that are not yet in play')
    @timeout(LOCAL_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_datacenter(self):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'datacenter_config.yaml')

        files_in_workspace = os.listdir(mypath)
        files = {f: os.path.join(mypath, f) for f in files_in_workspace if
                 os.path.isfile(os.path.join(mypath, f))}

        files['url'] = _file_url
        files['s3'] = _file_s3

        with get_local_queue_lock():
            self._run_test_files(
                n_experiments=2,
                files=files,
                config=config_path)

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS env variable to' +
        'use google cloud')
    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_gcspot(self):
        self._run_test_myfiles(
            n_experiments=2,
            config=self.get_config_path(),
            cloud='gcspot')

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS_DC' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS_DC env variable to' +
        'use google cloud')
    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_datacenter(self):
        oldcred = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = \
            os.environ['GOOGLE_APPLICATION_CREDENTIALS_DC']

        queue_name = 'test_queue_' + str(uuid.uuid4())

        self._run_test_myfiles(
            config=self.get_config_path('test_config_datacenter.yaml'),
            queue=queue_name,
            shutdown_del_queue=True
        )
        if oldcred:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = oldcred

    @unittest.skipIf(
        'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
        'Need GOOGLE_APPLICATION_CREDENTIALS env variable to' +
        'use google cloud')
    @timeout(CLOUD_TEST_TIMEOUT, use_signals=False)
    def test_two_experiments_gcloud(self):
        self._run_test_myfiles(
            n_experiments=2,
            config=self.get_config_path(),
            cloud='gcloud')

    @timeout(LOCAL_TEST_TIMEOUT, use_signals=False)
    def test_studiolink(self):

        experiment_id = str(uuid.uuid4())
        arg1 = random.randint(0, 10000)

        jobfile = self.get_jobfile('completion_service_testfunc_saveload.py')
        with CompletionService(experiment_id,
                               config=self.get_config_path(),
                               cloud_timeout=LOCAL_TEST_TIMEOUT) as cs:
            key1 = cs.submitTask(jobfile, arg1)
            ret_key1, result1 = cs.getResults()
            self.assertEquals(key1, ret_key1)
            self.assertEquals(result1, arg1)

            files = {
                'model': 'studio://{}/modeldir'.format(key1)
            }

            key2 = cs.submitTaskWithFiles(jobfile, None, files=files)
            ret_key2, result2 = cs.getResults()
            self.assertEquals(key2, ret_key2)
            self.assertEquals(result2, arg1 + 1)

    @timeout(LOCAL_TEST_TIMEOUT, use_signals=False)
    def test_restart(self):
        experiment_id = str(uuid.uuid4())
        arg1 = random.randint(0, 10000)

        jobfile = self.get_jobfile('completion_service_testfunc_saveload.py')
        with CompletionService(experiment_id,
                               config=self.get_config_path(),
                               cloud_timeout=LOCAL_TEST_TIMEOUT) as cs:
            key1 = cs.submitTask(jobfile, arg1, job_id=0)
            ret_key1, result1 = cs.getResults()
            self.assertEquals(key1, ret_key1)
            self.assertEquals(result1, arg1)

            key2 = cs.submitTask(jobfile, None, job_id=0)
            ret_key2, result2 = cs.getResults()
            self.assertEquals(key2, ret_key2)
            self.assertEquals(result2, arg1 + 1)

    def get_config_path(self, config_name='test_config_http_client.yaml'):
        mypath = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(
            mypath,
            '..',
            'tests',
            'test_config_http_client.yaml')

        return config_path

    def get_jobfile(self, filename='completion_service_testfunc.py'):
        mypath = os.path.dirname(os.path.realpath(__file__))
        jobfile = os.path.join(
            mypath, filename)

        return jobfile


if __name__ == '__main__':
    unittest.main()
