import os
import sys
import subprocess
import argparse
import yaml
import logging
import time
import json
import pip

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
        self.config = model.get_config()
        if args.config:
            if isinstance(args.config, basestring):
                with open(args.config) as f:
                    self.config.update(yaml.load(f))
            else:
                self.config.update(args.config)

        if args.guest:
            self.config['database']['guest'] = True

        self.db = model.get_db_provider(self.config)
        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(10)
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

        env = os.environ.copy()
        fs_tracker.setup_model_directory(env, experiment.key, clean=True)
        model_dir = fs_tracker.get_model_directory(experiment.key)
        log_path = os.path.join(model_dir, self.config['log']['name'])

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
                                 env=env)
            # simple hack to show what's in the log file
            ptail = subprocess.Popen(["tail", "-f", log_path])

            sched.add_job(
                lambda: self.db.checkpoint_experiment(experiment),
                'interval',
                minutes=self.config['saveWorkspaceFrequency'])

            try:
                p.wait()
            finally:
                ptail.kill()
                self.db.finish_experiment(experiment)
                sched.shutdown()


def allocate_resources(experiment, config=None):
    if not experiment.resources_needed:
        allocate_gpus(0, config)
        return True

    gpus_needed = experiment.resources_needed.get('gpus')
    ret_val = True
    if gpus_needed > 0:
        ret_val = ret_val and allocate_gpus(gpus_needed, config)
    else:
        allocate_gpus(0, config)

    return ret_val


def allocate_gpus(gpus_needed, config=None):
    available_gpus = get_available_gpus()
    gpu_mapping = get_gpu_mapping()
    if config and any(gpu_mapping):
        mapped_gpus = [str(gpu_mapping[g])
                       for g in available_gpus]
    else:
        mapped_gpus = [str(g) for g in available_gpus]

    if len(mapped_gpus) >= gpus_needed:
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(
            mapped_gpus[:gpus_needed])
        return True
    else:
        return False


def main(args=sys.argv):
    logger = logging.getLogger('studio-local-worker')
    logger.setLevel(10)
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio worker. \
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
                fetch_artifacts=False):

    logger = logging.getLogger('worker_loop')
    logger.setLevel(10)
    while queue.has_next():
        first_exp, ack_key = queue.dequeue(acknowledge=False)
        # first_exp = min([(p, os.path.getmtime(p)) for p in queue],
        #                key=lambda t: t[1])[0]

        experiment_key = json.loads(first_exp)['experiment']
        config = json.loads(first_exp)['config']
        parsed_args.config = config

        executor = LocalExecutor(parsed_args)
        experiment = executor.db.get_experiment(experiment_key)

        if allocate_resources(experiment, config):
            # os.remove(first_exp)
            queue.acknowledge(ack_key)
            if setup_pyenv:
                logger.info('Setting up python packages for experiment')
                pip.main(['install'] + experiment.pythonenv)

            if fetch_artifacts:
                logger.info('Fetching artifacts')
                # TODO rewrite with better artifact management
                executor.db._download_dir(
                    executor.db._get_experiments_keybase() +
                    experiment.key + '/workspace.tgz',
                    '.')
                pass

            executor.run(experiment)
            if single_experiment:
                logger.info('single_experiment is True, quitting')
                return
        else:
            logger.info('Cannot run experiment ' + experiment.key +
                        ' due lack of resources. Will retry')
            time.sleep(5)

        # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    logger.info("Queue in {} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))


if __name__ == "__main__":
    main()
