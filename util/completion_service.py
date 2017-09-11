import os
import subprocess
import uuid
import logging
import subprocess
import time
import pickle
import tempfile

from studio import runner, model

logging.basicConfig()


class CompletionServiceManager:
    def __init__(
            self,
            config=None,
            resources_needed=None,
            cloud=None,
            verbose=10):
        self.config = config
        self.experimentId = experimentId
        self.project_name = "completion_service_" + experimentId
        self.queue_name = project_name
        self.resources_needed = resources_needed
        self.wm = runner.get_worker_manager(config, cloud)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        self.queue = runner.get_queue(queue_name, self.cloud, verbose)

        self.completion_services = {}

    def submitTask(self, experimentId, clientCodeFile, args):
        if experimentId not in self.completion_services.keys():
            self.completion_services[experimentId] = \
                CompletionService(
                    experimentId,
                    self.config,
                    self.resources_needed,
                    self.cloud,
                    self.verbose).__enter__()

        return self.completion_services[experimentId].submitTask(
            clientCodeFile, args)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for _, cs in self.completion_services.iter_items():
            cs.__exit__()


class CompletionService:

    def __init__(
            self,
            experimentId,
            config=None,
            resources_needed=None,
            cloud=None,
            verbose=10):
        self.config = model.get_config(config)
        self.cloud = None
        self.experimentId = experimentId
        self.project_name = "completion_service_" + experimentId
        self.queue_name = 'local'
        self.resources_needed = resources_needed
        self.wm = runner.get_worker_manager(config, cloud)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        self.queue = runner.get_queue(self.queue_name, self.cloud, verbose)

        self.bid = '100%'
        self.cloud_timeout = 100

    def __enter__(self):
        if self.wm:
            self.wm.start_spot_workers(
                self.queue_name,
                self.bid,
                self.resources_needed,
                start_workers=1,
                queue_upscaling=True,
                ssh_keypair='peterz-k1',
                timeout=self.cloud_timeout)
        else:
            self.p = subprocess.Popen([
                'studio-local-worker',
                '--verbose=error',
                '--timeout=' + str(self.cloud_timeout)],
                close_fds=True)

        return self

    def __exit__(self, *args):
        if self.queue_name != 'local':
            self.queue.delete()

        if self.p:
            self.p.wait()

    def submitTaskWithFiles(self, clientCodeFile, args, files={}):
        cwd = os.path.dirname(os.path.realpath(__file__)),
        experiment_name = self.project_name + "_" + str(uuid.uuid4())

        tmpdir = tempfile.gettempdir()
        args_file = os.path.join(tmpdir, experiment_name + "_args.pkl")

        artifacts = {
            'retval': {
                'mutable': True
            },
            'clientscript': {
                'mutable': False,
                'local': clientCodeFile
            },
            'args': {
                'mutable': False,
                'local': args_file
            }
        }

        for tag, name in files.iteritems():
            artifacts[tag] = {
                'mutable': False,
                'local': name
            }

        with open(args_file, 'w') as f:
            f.write(pickle.dumps(args))

        experiment = model.create_experiment(
            'completion_service_client.py',
            [],
            experiment_name=experiment_name,
            project=self.project_name,
            artifacts=artifacts,
            resources_needed=self.resources_needed)

        runner.submit_experiments(
            [experiment],
            config=self.config,
            logger=self.logger,
            cloud=self.cloud,
            queue_name=self.queue_name)

        return experiment_name

    def submitTask(self, clientCodeFile, args):
        return self.submitTaskWithFiles(clientCodeFile, args, {})

    def getResultsWithTimeout(self, timeout=0):
        retval = {}

        total_sleep_time = 0
        sleep_time = 1

        while True:
            with model.get_db_provider(self.config) as db:
                experiments = db.get_project_experiments(self.project_name)

            for e in experiments:
                if e.status == 'finished':
                    with open(db.get_artifact(e.artifacts['retval'])) as f:
                        data = pickle.load(f)

                    retval[e.key] = data
            if all([e.status == 'finished' for e in experiments]) or \
               timeout == 0 or \
               (timeout > 0 and total_sleep_time > timeout):
                    break

            time.sleep(sleep_time)
            total_sleep_time += sleep_time
    
        return retval

    def getResults(self, blocking=False):
        return self.getResultsWithTimeout(-1 if blocking else 0)
