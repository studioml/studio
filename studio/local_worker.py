import os
import sys
import subprocess
import argparse
import yaml
import logging
import time
import json

from apscheduler.schedulers.background import BackgroundScheduler

import fs_tracker
import model
from local_queue import LocalQueue
from gpu_util import get_available_gpus, get_gpu_mapping

logging.basicConfig()


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.
    """

    def __init__(self, args):
        self.config = args.config

        if args.guest:
            self.config['database']['guest'] = True

        self.db = model.get_db_provider(self.config)
        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(model.parse_verbosity(self.config.get('verbose')))
        self.logger.debug("Config: ")
        self.logger.debug(self.config)

    def run(self, experiment):
        if isinstance(experiment, basestring):
            experiment = self.db.get_experiment(experiment)
        elif not isinstance(experiment, model.Experiment):
            raise ValueError("Unknown type of experiment: " +
                             str(type(experiment)))

        self.logger.info("Experiment key: " + experiment.key)

        self.db.start_experiment(experiment)

        """ Override env variables with those inside the queued message
        """
        env = dict(os.environ)
        if 'env' in self.config.keys():
            for k, v in self.config['env'].iteritems():
                if v is not None:
                    env[str(k)] = str(v)

        fs_tracker.setup_experiment(env, experiment, clean=True)
        log_path = fs_tracker.get_artifact_cache('output', experiment.key)

        # log_path = os.path.join(model_dir, self.config['log']['name'])

        self.logger.debug('Child process environment:')
        self.logger.debug(str(env))

        sched = BackgroundScheduler()
        sched.start()

        with open(log_path, 'w') as output_file:
            p = subprocess.Popen(["python",
                                  experiment.filename] +
                                 experiment.args,
                                 stdout=output_file,
                                 stderr=subprocess.STDOUT,
                                 env=env,
                                 cwd=experiment
                                 .artifacts['workspace']['local'],
                                 close_fds=True)
            # simple hack to show what's in the log file
            ptail = subprocess.Popen(["tail", "-f", log_path], close_fds=True)

            sched.add_job(
                lambda: self.db.checkpoint_experiment(experiment),
                'interval',
                minutes=self.config['saveWorkspaceFrequencyMinutes'])

            def kill_if_stopped():
                if self.db.get_experiment(
                        experiment.key,
                        getinfo=False).status == 'stopped':
                    p.kill()

            sched.add_job(kill_if_stopped, 'interval', seconds=10)

            try:
                p.wait()
            finally:
                ptail.kill()
                self.db.finish_experiment(experiment)
                sched.shutdown()


def allocate_resources(experiment, config=None, verbose=10):
    logger = logging.getLogger('allocate_resources')
    logger.setLevel(verbose)
    logger.info('Allocating resources {} for experiment {}'
                .format(experiment.resources_needed, experiment.key))

    ret_val = True
    gpus_needed = int(experiment.resources_needed.get('gpus')) \
        if experiment.resources_needed else 0

    pythonenv_nogpu = [pkg for pkg in experiment.pythonenv
                       if not pkg.startswith('tensorflow-gpu')]

    if gpus_needed > 0:
        ret_val = ret_val and allocate_gpus(gpus_needed, config)
        # experiments with GPU should have tensorflow-gpu version
        # matching tensorflow version

        tensorflow_pkg = [pkg for pkg in experiment.pythonenv
                          if pkg.startswith('tensorflow==')][0]

        experiment.pythonenv = pythonenv_nogpu + \
            [tensorflow_pkg.replace('tensorflow==', 'tensorflow-gpu==')]

    else:
        allocate_gpus(0, config)
        # experiments without GPUs should not have
        # tensorflow-gpu package in the evironment, because it won't
        # work on the machines that do not have cuda installed
        experiment.pythonenv = pythonenv_nogpu

    return ret_val


def allocate_gpus(gpus_needed, config=None):
    if gpus_needed <= 0:
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        return True

    available_gpus = get_available_gpus()
    gpu_mapping = get_gpu_mapping()
    mapped_gpus = [str(gpu_mapping[g])
                   for g in available_gpus]

    if len(mapped_gpus) >= gpus_needed:
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(
            mapped_gpus[:gpus_needed])
        return True
    else:
        return False


def main(args=sys.argv):
    parser = argparse.ArgumentParser(
        description='Studio worker. \
                     Usage: studio-local-worker \
                     ')

    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parsed_args, script_args = parser.parse_known_args(args)

    queue = LocalQueue()
    # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    worker_loop(queue, parsed_args)


def worker_loop(queue, parsed_args,
                setup_pyenv=False,
                single_experiment=False,
                fetch_artifacts=False,
                timeout=0):

    logger = logging.getLogger('worker_loop')

    hold_period = 4
    while queue.has_next():

        first_exp, ack_key = queue.dequeue(acknowledge=False)

        experiment_key = json.loads(first_exp)['experiment']['key']
        config = json.loads(first_exp)['config']
        parsed_args.config = config
        verbose = model.parse_verbosity(config.get('verbose'))
        logger.setLevel(verbose)

        logger.debug('Received experiment {} with config {} from the queue'.
                     format(experiment_key, config))

        executor = LocalExecutor(parsed_args)
        experiment = executor.db.get_experiment(experiment_key)

        if allocate_resources(experiment, config, verbose=verbose):
            def hold_job():
                queue.hold(ack_key, hold_period)

            hold_job()
            sched = BackgroundScheduler()
            sched.add_job(hold_job, 'interval', minutes=hold_period / 2)
            sched.start()

            try:
                if setup_pyenv:
                    logger.info('Setting up python packages for experiment')
                    pipp = subprocess.Popen(
                        ['pip', 'install'] + experiment.pythonenv,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)

                    pipout, _ = pipp.communicate()
                    logger.info("pip output: \n" + pipout)

                    # pip.main(['install'] + experiment.pythonenv)

                for tag, art in experiment.artifacts.iteritems():
                    if fetch_artifacts or 'local' not in art.keys():
                        logger.info('Fetching artifact ' + tag)
                        if tag == 'workspace':
                            # art['local'] = executor.db.store.get_artifact(
                            #    art, '.', only_newer=False)
                            art['local'] = executor.db.get_artifact(
                                art, only_newer=False)
                        else:
                            art['local'] = executor.db.get_artifact(art)
                executor.run(experiment)
            finally:
                sched.shutdown()
                queue.acknowledge(ack_key)

            if single_experiment:
                logger.info('single_experiment is True, quitting')
                return
        else:
            logger.info('Cannot run experiment ' + experiment.key +
                        ' due lack of resources. Will retry')
            time.sleep(config['sleep_time'])

        wait_for_messages(queue, timeout, logger)

        # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    logger.info("Queue in {} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))


def wait_for_messages(queue, timeout, logger=None):
    wait_time = 0
    wait_step = 5
    timeout = int(timeout)
    if timeout == 0:
        return

    while not queue.has_next():
        if logger:
            logger.info(
                'No messages found, sleeping for {} s (total wait time {} s)'
                .format(wait_step, wait_time))
        time.sleep(wait_step)
        wait_time += wait_step
        if timeout > 0 and timeout < wait_time:
            if logger:
                logger.info('No jobs found in the queue during {} s'.
                            format(timeout))
            return


if __name__ == "__main__":
    main()
