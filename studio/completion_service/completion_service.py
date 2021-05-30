import os
import subprocess
import uuid
import pickle
import tempfile
import re
import six
import time

from studio import experiment_submitter, model, fs_tracker, logs
from studio.util import rsync_cp, parse_verbosity
from studio.experiment import create_experiment

DEFAULT_RESOURCES_NEEDED = {
    'cpus': 2,
    'ram': '3g',
    'hdd': '10g',
    'gpus': 0
}

RESUMABLE = False
CLEAN_QUEUE = True
QUEUE_UPSCALING = False

class CompletionService:

    def __init__(
        self,
        # Name of experiment
        experimentId,
        # Completion service configuration
        cs_config=None,
        # used to pass a studioML configuration block read by client software
        studio_config=None,
        # Studio config yaml file
        studio_config_file=None,
        shutdown_del_queue=False
    ):
        # StudioML configuration
        self.config = model.get_config(studio_config_file)

        self.logger = logs.get_logger(self.__class__.__name__)
        self.verbose_level = parse_verbosity(self.config['verbose'])
        self.logger.setLevel(self.verbose_level)

        # Setup Completion Service instance properties
        # based on configuration
        self.experimentId = experimentId
        self.project_name = "completion_service_" + experimentId

        self.resumable = RESUMABLE
        self.clean_queue = CLEAN_QUEUE
        self.queue_upscaling = QUEUE_UPSCALING
        self.num_workers = int(cs_config.get('num_workers', 1))
        self.cloud_timeout = cs_config.get('timeout')
        self.bid = cs_config.get('bid')
        self.ssh_keypair = cs_config.get('ssh_keypair')
        self.sleep_time = cs_config.get('sleep_time')
        self.shutdown_del_queue = shutdown_del_queue

        # Figure out request for resources:
        resources_needed = cs_config.get('resources_needed')
        self.resources_needed = DEFAULT_RESOURCES_NEEDED
        self.resources_needed.update(resources_needed)
        studio_resources = self.config.get('resources_needed')
        if studio_resources:
            self.resources_needed.update(studio_resources)

        # Figure out task queue and cloud we are going to use:
        queue_name = cs_config.get('queue')
        cloud_name = cs_config.get('cloud')
        if cs_config.get('local'):
            queue_name = None
            cloud_name = None
        elif queue_name is not None:
            self.shutdown_del_queue = False
            if cloud_name in ['ec2spot', 'ec2']:
                assert queue_name.startswith("sqs_")
        else:
            queue_name = self.experiment_id
            if cloud_name in ['ec2spot', 'ec2']:
                queue_name = "sqs_" + queue_name
        self.cloud = cloud_name
        if queue_name is not None and queue_name.startswith("rmq_"):
            assert self.cloud is None

        self.wm = model.get_worker_manager(
            self.config, self.cloud)

        if queue_name is not None:
            self.logger.info(
                "CompletionService configured with queue {0}"
                    .format(queue_name))

        self.queue = model.get_queue(queue_name=queue_name, cloud=self.cloud,
                                      config=self.config,
                                      logger=self.logger,
                                      verbose=self.verbose_level)

        self.queue_name = self.queue.get_name()

        self.submitted = {}
        self.use_spot = cloud_name in ['ec2spot', 'gcspot']

        self.logger.info("Project name: {0}".format(self.project_name))
        self.logger.info("Initial/final queue name: {0}, {1}"
                         .format(queue_name, self.queue_name))
        self.logger.info("Cloud name: {0}".format(self.cloud))

    def __enter__(self):
        with model.get_db_provider(self.config):
            pass
        self.p = None
        if self.wm:
            self.logger.debug('Spinning up cloud workers')
            if self.use_spot:
                self.wm.start_spot_workers(
                    self.queue_name,
                    self.bid,
                    self.resources_needed,
                    start_workers=self.num_workers,
                    queue_upscaling=self.queue_upscaling,
                    ssh_keypair=self.ssh_keypair,
                    timeout=self.cloud_timeout)
            else:
                for i in range(self.num_workers):
                    self.wm.start_worker(
                        self.queue_name,
                        self.resources_needed,
                        ssh_keypair=self.ssh_keypair,
                        timeout=self.cloud_timeout)

        elif self.queue_name is None or self.queue_name == 'local':
            self.logger.debug('Starting local worker')
            self.p = subprocess.Popen([
                'studio-local-worker',
                '--verbose=%s' % self.config['verbose'],
                '--timeout=' + str(self.cloud_timeout)],
                close_fds=True)

        # yet another case is when queue name is specified, but
        # cloud is not - that means running on a separately
        # managed server that listens to the queue
        #
        # The contract is queue_name that starts with sqs or ec2
        # is an SQS queue, otherwise, it is a PubSub queue

        return self

    def __exit__(self, *args):
        self.close()

    def close(self, delete_queue=True):
        self.logger.info("Studioml completion service shutting down")
        request_delete_queue = self.shutdown_del_queue or delete_queue
        model.shutdown_queue(self.queue, self.logger, request_delete_queue)

    def submitTaskWithFiles(
            self,
            clientCodeFile,
            args,
            files={},
            job_id=None):
        old_cwd = os.getcwd()
        cwd = os.path.dirname(os.path.realpath(__file__))
        os.chdir(cwd)

        if job_id is not None:
            experiment_name = self.project_name + "_" + str(job_id)
        else:
            experiment_name = self.project_name + "_" + str(uuid.uuid4())

        tmpdir = tempfile.gettempdir()
        args_file = os.path.join(tmpdir, experiment_name + "_args.pkl")

        workspace_orig = os.getcwd()
        ignore_arg = ''
        ignore_filepath = os.path.join(workspace_orig, ".studioml_ignore")
        if os.path.exists(ignore_filepath) and \
                not os.path.isdir(ignore_filepath):
            ignore_arg = "--exclude-from=%s" % ignore_filepath

        workspace_new = fs_tracker.get_artifact_cache(
            'workspace', experiment_name)
        rsync_cp(workspace_orig, workspace_new, ignore_arg, self.logger)
        distpath = os.path.join(old_cwd, 'dist')
        if os.path.exists(distpath):
            self.logger.info('dist folder found at {}, ' +
                             'copying into workspace')
            rsync_cp(distpath, os.path.join(workspace_new, 'dist'))

        self.logger.info('Created workspace ' + workspace_new)

        artifacts = self._create_artifacts(
            clientCodeFile, args_file, workspace_new, files)

        with open(args_file, 'wb') as f:
            f.write(pickle.dumps(args, protocol=2))

        experiment = create_experiment(
            'completion_service_client.py',
            [self.config['verbose']],
            experiment_name=experiment_name,
            project=self.project_name,
            artifacts=artifacts,
            resources_needed=self.resources_needed)

        tic = time.time()
        experiment_submitter.submit_experiments(
            [experiment],
            config=self.config,
            logger=self.logger,
            queue=self.queue)

        self.submitted[experiment.key] = time.time()
        os.chdir(old_cwd)
        toc = time.time()
        self.logger.info('Submitted experiment ' + experiment.key +
                         ' in ' + str(toc - tic) + ' s')

        return experiment_name

    def submitTask(self, clientCodeFile, args, job_id=None):
        return self.submitTaskWithFiles(
            clientCodeFile, args, {}, job_id=job_id)

    def getResultsWithTimeout(self, timeout=0):
        total_sleep_time = 0
        sleep_time = self.sleep_time

        assert self.resumable is False

        while True:
            with model.get_db_provider(self.config) as db:

                for key, submitted_time in six.iteritems(self.submitted):
                    try:
                        e = db.get_experiment(key)
                        if e is not None:
                            retval_path = db.get_artifact(
                                e.artifacts['retval'])
                            if os.path.exists(retval_path) and \
                               os.path.getmtime(retval_path) > submitted_time:
                                with open(retval_path, 'rb') as f:
                                    data = pickle.load(f)

                                del self.submitted[e.key]
                                return (e.key, data)
                    except BaseException as e:
                        self.logger.debug(
                            "Getting result failed due to exception:")
                        self.logger.debug(e)

                    '''
                    if e is not None and e.status == 'finished':
                        self.logger.debug(
                            'Experiment {} finished, getting results' .format(
                                e.key))
                        with open(db.get_artifact(e.artifacts['retval']),
                                  'rb') as f:
                            data = pickle.load(f)

                        if not self.resumable:
                            self.submitted.remove(e.key)
                        else:
                            db.delete_experiment(e.key)

                        return (e.key, data)
                    '''

            if timeout == 0 or \
               (timeout > 0 and total_sleep_time > timeout):
                return None

            if self.p is not None:
                assert self.p.poll() is None, \
                    "Executor process died, no point in waiting for results"

            time.sleep(sleep_time)
            total_sleep_time += sleep_time

    def getResults(self, blocking=True):
        return self.getResultsWithTimeout(-1 if blocking else 0)

    def _create_artifacts(
            self,
            client_code_file,
            args_file,
            workspace_new,
            files):
        artifacts = {
            'retval': {
                'mutable': True,
                'unpack': True
            },
            'clientscript': {
                'mutable': False,
                'local': client_code_file,
                'unpack': True
            },
            'args': {
                'mutable': False,
                'local': args_file,
                'unpack': True
            },
            'workspace': {
                'mutable': False,
                'local': workspace_new,
                'unpack': True
            }
        }

        for tag, name in six.iteritems(files):
            artifacts[tag] = {}
            url_schema = re.compile('^https{0,1}://')
            s3_schema = re.compile('^s3://')
            gcs_schema = re.compile('^gs://')
            studio_schema = re.compile(
                'studio://(?P<experiment>.+)/(?P<artifact>.+)')

            if url_schema.match(name):
                artifacts[tag]['url'] = name
                artifacts[tag]['unpack'] = False
            elif s3_schema.match(name) or gcs_schema.match(name):
                artifacts[tag]['qualified'] = name
                artifacts[tag]['unpack'] = False
            elif studio_schema.match(name):
                ext_experiment_key = studio_schema.match(
                    name).group('experiment')
                ext_tag = studio_schema.match(name).group('artifact')
                with model.get_db_provider(self.config) as db:
                    ext_experiment = db.get_experiment(ext_experiment_key)

                artifacts[tag]['key'] = \
                    ext_experiment.artifacts[ext_tag]['key']
                artifacts[tag]['unpack'] = True
            else:
                artifacts[tag]['local'] = os.path.abspath(
                    os.path.expanduser(name))
                artifacts[tag]['unpack'] = True

            artifacts[tag]['mutable'] = False

        return artifacts
