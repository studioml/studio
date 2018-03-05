import os
import subprocess
import uuid
import pickle
import tempfile
import re
import six
import time

from studio import runner, model, fs_tracker, logs
from studio.util import rsync_cp
from studio.experiment import create_experiment


'''
class CompletionServiceManager:
    def __init__(
            self,
            config=None,
            resources_needed=None,
            cloud=None):
        self.config = config
        self.resources_needed = resources_needed
        self.wm = runner.get_worker_manager(config, cloud)
        self.logger = logs.getLogger(self.__class__.__name__)
        verbose = model.parse_verbosity(self.config['verbose'])
        self.logger.setLevel(verbose)

        self.queue = runner.get_queue(self.cloud, verbose)

        self.completion_services = {}

    def submitTask(self, experimentId, clientCodeFile, args):
        if experimentId not in self.completion_services.keys():
            self.completion_services[experimentId] = \
                CompletionService(
                    experimentId,
                    self.config,
                    self.resources_needed,
                    self.cloud).__enter__()

        return self.completion_services[experimentId].submitTask(
            clientCodeFile, args)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for _, cs in self.completion_services.iter_items():
            cs.__exit__()
'''

DEFAULT_RESOURCES_NEEDED = {
    'cpus': 2,
    'ram': '3g',
    'hdd': '10g',
    'gpus': 0
}


class CompletionService:

    def __init__(
        self,
        # Name of experiment
        experimentId,
        # Config yaml file
        config=None,
        # Number of remote workers to spin up
        num_workers=1,
        # Compute requirements, amount of RAM, GPU, etc
        resources_needed={},
        # Name of the queue for submission to a server.
        queue=None,
        # What computer resource to use, either AWS, Google, or local
        cloud=None,
        # Timeout for cloud instances
        cloud_timeout=100,
        # Bid price for EC2 spot instances
        bid='100%',
        # Keypair to use for EC2 workers
        ssh_keypair=None,
        # If true, get results that are submitted by other instances of CS
        resumable=False,
        # Whether to clean the submission queue on initialization
        clean_queue=True,
        # Whether to enable autoscaling for EC2 instances
        queue_upscaling=True,
        # Whether to delete the queue on shutdown
        shutdown_del_queue=False,
        # delay between queries for results
        sleep_time=1
    ):

        self.config = model.get_config(config)
        self.cloud = cloud
        self.experimentId = experimentId
        self.project_name = "completion_service_" + experimentId

        self.resources_needed = DEFAULT_RESOURCES_NEEDED
        if self.config.get('resources_needed'):
            self.resources_needed.update(self.config.get('resources_needed'))

        self.resources_needed.update(resources_needed)

        self.wm = runner.get_worker_manager(
            self.config, self.cloud)

        self.logger = logs.getLogger(self.__class__.__name__)
        self.verbose_level = model.parse_verbosity(self.config['verbose'])
        self.logger.setLevel(self.verbose_level)

        self.queue = runner.get_queue(queue, self.cloud,
                                      self.verbose_level)

        self.queue_name = self.queue.get_name()

        self.clean_queue = clean_queue
        if self.clean_queue:
            self.queue.clean()

        self.cloud_timeout = cloud_timeout
        self.bid = bid
        self.ssh_keypair = ssh_keypair

        self.submitted = set([])
        self.num_workers = num_workers
        self.resumable = resumable
        self.queue_upscaling = queue_upscaling
        self.shutdown_del_queue = shutdown_del_queue
        self.use_spot = cloud in ['ec2spot', 'gcspot']
        self.sleep_time = sleep_time

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
        # if self.queue_name != 'local' and delete_queue:
        if self.shutdown_del_queue:
            self.queue.delete()

        if self.p:
            self.p.kill()
            # os.kill(self.p.pid, signal.SIGKILL)

    def submitTaskWithFiles(self, clientCodeFile, args, files={}):
        old_cwd = os.getcwd()
        cwd = os.path.dirname(os.path.realpath(__file__))
        os.chdir(cwd)

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
        runner.submit_experiments(
            [experiment],
            config=self.config,
            logger=self.logger,
            cloud=self.cloud,
            queue_name=self.queue_name)

        self.submitted.add(experiment.key)
        os.chdir(old_cwd)
        toc = time.time()
        self.logger.info('Submitted experiment ' + experiment.key +
                         ' in ' + str(toc - tic) + ' s')

        return experiment_name

    def submitTask(self, clientCodeFile, args):
        return self.submitTaskWithFiles(clientCodeFile, args, {})

    def getResultsWithTimeout(self, timeout=0):
        total_sleep_time = 0
        sleep_time = self.sleep_time

        while True:
            with model.get_db_provider(self.config) as db:
                if self.resumable:
                    experiment_keys = db.get_project_experiments(
                        self.project_name).keys()
                else:
                    experiment_keys = self.submitted

                for key in experiment_keys:
                    try:
                        e = db.get_experiment(key)
                        if e is not None:
                            retval_path = db.get_artifact(
                                e.artifacts['retval'])
                            if os.path.exists(retval_path):
                                with open(retval_path, 'rb') as f:
                                    data = pickle.load(f)

                                if not self.resumable:
                                    self.submitted.remove(e.key)
                                else:
                                    db.delete_experiment(e.key)

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
