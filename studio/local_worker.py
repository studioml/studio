import os
import sys
import subprocess
import argparse
import logging
import json
import psutil
import time
import six


from apscheduler.schedulers.background import BackgroundScheduler

from . import fs_tracker
from . import model
from .local_queue import LocalQueue
from .gpu_util import get_available_gpus, get_gpu_mapping, get_gpus_summary
from .experiment import Experiment
from .util import sixdecode, str2duration

logging.basicConfig()
logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.
    """

    def __init__(self, args):
        self.config = args.config

        if args.guest:
            self.config['database']['guest'] = True

        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(model.parse_verbosity(self.config.get('verbose')))
        self.logger.debug("Config: ")
        self.logger.debug(self.config)

    def run(self, experiment):
        if isinstance(experiment, six.string_types):
            experiment = self.db.get_experiment(experiment)
        elif not isinstance(experiment, Experiment):
            raise ValueError("Unknown type of experiment: " +
                             str(type(experiment)))

        self.logger.info("Experiment key: " + experiment.key)

        with model.get_db_provider(self.config) as db:
            db.start_experiment(experiment)

            """ Override env variables with those inside the queued message
            """
            env = dict(os.environ)
            if 'env' in self.config.keys():
                for k, v in six.iteritems(self.config['env']):
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
                python = 'python'
                if experiment.pythonver == 3:
                    python = 'python3'

                p = subprocess.Popen([python,
                                      experiment.filename] +
                                     experiment.args,
                                     stdout=output_file,
                                     stderr=subprocess.STDOUT,
                                     env=env,
                                     cwd=experiment
                                     .artifacts['workspace']['local'])
                # simple hack to show what's in the log file
                ptail = subprocess.Popen(["tail", "-f", log_path])

                minutes = 0
                if self.config.get('saveWorkspaceFrequency'):
                    minutes = int(
                        str2duration(
                            self.config['saveWorkspaceFrequency'])
                        .total_seconds() / 60)

                sched.add_job(
                    lambda: db.checkpoint_experiment(experiment),
                    'interval',
                    minutes=minutes)

                metrics_path = fs_tracker.get_artifact_cache(
                    '_metrics', experiment.key)

                minutes = 0
                if self.config.get('saveMetricsFrequency'):
                    minutes = int(
                        str2duration(
                            self.config['saveMetricsFrequency'])
                        .total_seconds() / 60)

                sched.add_job(
                    lambda: save_metrics(metrics_path),
                    'interval',
                    minutes=minutes)

                def kill_if_stopped():
                    if db.get_experiment(
                            experiment.key,
                            getinfo=False).status == 'stopped':
                        p.kill()

                    if experiment.max_duration is not None and \
                            time.time() > experiment.time_started + \
                            int(str2duration(experiment.max_duration)
                                .total_seconds()):

                        p.kill()

                sched.add_job(kill_if_stopped, 'interval', seconds=10)

                try:
                    p.wait()
                finally:
                    save_metrics(metrics_path)
                    sched.shutdown()
                    ptail.kill()
                    db.checkpoint_experiment(experiment)
                    db.finish_experiment(experiment)


def allocate_resources(experiment, config=None, verbose=10):
    logger = logging.getLogger('allocate_resources')
    logger.setLevel(verbose)
    logger.info('Allocating resources {} for experiment {}'
                .format(experiment.resources_needed, experiment.key))

    ret_val = True
    gpus_needed = int(experiment.resources_needed.get('gpus')) \
        if experiment.resources_needed else 0

    if gpus_needed > 0:
        ret_val = ret_val and allocate_gpus(gpus_needed, config)
    else:
        allocate_gpus(0, config)

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
    parser.add_argument(
        '--timeout',
        default=0, type=int)

    parsed_args, script_args = parser.parse_known_args(args)

    queue = LocalQueue()
    # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")
    # wait_for_messages(queue, parsed_args.timeout)
    worker_loop(queue, parsed_args, timeout=parsed_args.timeout)


def worker_loop(queue, parsed_args,
                single_experiment=False,
                timeout=0,
                verbose=None):

    fetch_artifacts = True

    logger = logging.getLogger('worker_loop')

    hold_period = 4
    while True:
        msg = queue.dequeue(acknowledge=False, timeout=timeout)
        if not msg:
            break

        # first_exp, ack_key = queue.dequeue(acknowledge=False)
        first_exp, ack_key = msg

        data_dict = json.loads(sixdecode(first_exp))
        experiment_key = data_dict['experiment']['key']
        config = data_dict['config']

        parsed_args.config = config
        if verbose:
            config['verbose'] = verbose
        else:
            verbose = model.parse_verbosity(config.get('verbose'))

        logger.setLevel(verbose)

        logger.debug('Received experiment {} with config {} from the queue'.
                     format(experiment_key, config))

        executor = LocalExecutor(parsed_args)

        with model.get_db_provider(config) as db:
            experiment = db.get_experiment(experiment_key)

            if config.get('experimentLifetime') and \
                int(str2duration(config['experimentLifetime'])
                    .total_seconds()) + experiment.time_added < time.time():
                logger.info(
                    'Experiment expired (max lifetime of {} was exceeded)'
                    .format(config.get('experimentLifetime'))
                )
                queue.acknowledge(ack_key)
                continue

            if allocate_resources(experiment, config, verbose=verbose):
                def hold_job():
                    queue.hold(ack_key, hold_period)

                hold_job()
                sched = BackgroundScheduler()
                sched.add_job(hold_job, 'interval', minutes=hold_period / 2)
                sched.start()

                try:
                    python = 'python'
                    if experiment.pythonver == 3:
                        python = 'python3'
                    pip_diff = pip_needed_packages(
                        experiment.pythonenv, python)
                    if any(pip_diff):
                        logger.info(
                            'Setting up python packages for experiment')
                        if pip_install_packages(pip_diff, python, logger) != 0:
                            logger.info(
                                "Installation of all packages together " +
                                " failed, "
                                "trying one package at a time")

                            for pkg in pip_diff:
                                pip_install_packages([pkg], python, logger)

                    for tag, art in six.iteritems(experiment.artifacts):
                        if fetch_artifacts or 'local' not in art.keys():
                            logger.info('Fetching artifact ' + tag)
                            if tag == 'workspace':
                                art['local'] = db.get_artifact(
                                    art, only_newer=False)
                            else:
                                art['local'] = db.get_artifact(art)
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

        # wait_for_messages(queue, timeout, logger)

        # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    logger.info("Queue in {} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))


def pip_install_packages(packages, python='python', logger=None):
    pipp = subprocess.Popen(
        [python, '-m', 'pip', 'install'] + [p for p in packages],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    pipout, _ = pipp.communicate()
    pipout = pipout.decode('utf-8')
    # return pip.main(['install'] + list(packages))

    if logger:
        logger.info("pip output: \n" + pipout)
    return pipp.returncode


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


def save_metrics(path):
    cpu_load = psutil.cpu_percent()
    cpu_mem = psutil.virtual_memory().used
    timestamp = time.time()
    with open(path, 'a') as f:
        entry = 'time: {} CPU: {} mem: {} {} \n' \
                .format(
                    timestamp,
                    cpu_load,
                    cpu_mem,
                    get_gpus_summary())

        f.write(entry)


def pip_needed_packages(packages, python='python'):

    pipp = subprocess.Popen(
        [python, '-m', 'pip', 'freeze'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)

    pipout, _ = pipp.communicate()
    pipout = pipout.decode('utf-8')
    current_packages = {l.strip() for l in pipout.strip().split('\n')}

    # current_packages = {p._key + '==' + p._version for p in
    #                    pip.pip.get_installed_distributions(local_only=True)}

    return {p for p in packages} - current_packages


if __name__ == "__main__":
    main()
