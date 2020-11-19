import os
import sys
import subprocess
import argparse
import json
import psutil
import time
import six
import signal
import pdb

from apscheduler.schedulers.background import BackgroundScheduler

from . import fs_tracker, model, logs
from .local_queue import LocalQueue
from .gpu_util import get_available_gpus, get_gpu_mapping, get_gpus_summary
from .artifact import Artifact
from .experiment import Experiment
from .util import sixdecode, str2duration, retry, LogReprinter, parse_verbosity

logs.getLogger('apscheduler.scheduler').setLevel(logs.ERROR)


class LocalExecutor(object):
    """Runs job while capturing environment and logs results.
    """

    def __init__(self, queue, args):
        self.config = args.config

        if args.guest:
            self.config['database']['guest'] = True

        self.task_queue = queue
        self.logger = logs.getLogger('LocalExecutor')
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

            env['PYTHONUNBUFFERED'] = 'TRUE'

            fs_tracker.setup_experiment(env, experiment, clean=False)
            log_path = fs_tracker.get_artifact_cache('output', experiment.key)

            # log_path = os.path.join(model_dir, self.config['log']['name'])

            self.logger.debug('Child process environment:')
            self.logger.debug(str(env))

            sched = BackgroundScheduler()
            sched.start()

            with open(log_path, 'w') as output_file:
                python = 'python'
                if experiment.pythonver[0] == '3':
                    python = 'python3'

                python = which(python)

                cmd = [python, experiment.filename] + experiment.args
                cwd = experiment.artifacts['workspace'].local_path
                container_artifact = experiment.artifacts.get('_singularity')
                if container_artifact:
                    container = container_artifact.get('local')
                    if not container:
                        container = container_artifact.get('qualified')

                    cwd = fs_tracker.get_artifact_cache(
                        'workspace', experiment.key)

                    for tag, art in six.iteritems(experiment.artifacts):
                        local_path = art.get('local')
                        if not art['mutable'] and os.path.exists(local_path):
                            os.symlink(
                                art['local'],
                                os.path.join(os.path.dirname(cwd), tag)
                            )

                    if experiment.filename is not None:
                        cmd = [
                            'singularity',
                            'exec',
                            container,
                        ] + cmd
                    else:
                        cmd = ['singularity', 'run', container]

                self.logger.info('Running cmd: {0} in {1}'.format(cmd, cwd))

                p = subprocess.Popen(
                    cmd,
                    stdout=output_file,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=cwd
                )

                run_log_reprinter = True
                log_reprinter = LogReprinter(log_path)
                if run_log_reprinter:
                    log_reprinter.run()

                def kill_subprocess():
                    log_reprinter.stop()
                    p.kill()

                minutes = 0
                if self.config.get('saveWorkspaceFrequency'):
                    minutes = int(
                        str2duration(
                            self.config['saveWorkspaceFrequency'])
                        .total_seconds() / 60)

                def checkpoint():
                    try:
                        db.checkpoint_experiment(experiment)
                    except BaseException as e:
                        self.logger.info(e)

                sched.add_job(
                    checkpoint,
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
                    try:
                        db_expr = db.get_experiment(
                            experiment.key,
                            getinfo=False)
                    except:
                        db_expr = None

                    # Transient issues with getting experiment data might
                    # result in a None value being returned, as result
                    # leave the experiment running because we wont be able to
                    # do anything else even if this experiment is stopped
                    # in any event if the experiment runs too long then it
                    # will exceed its allocated time and stop
                    if db_expr is not None:
                        if db_expr.status == 'stopped':
                            kill_subprocess()
                            return

                    if experiment.max_duration is not None and \
                            time.time() > experiment.time_started + \
                            int(str2duration(experiment.max_duration)
                                .total_seconds()):

                        kill_subprocess()
                        return

                    # If our tasks queue is signalled inactive
                    # during work process execution, that means we need to drop
                    # current execution and exit
                    if not self.task_queue.is_active():
                        kill_subprocess()

                sched.add_job(kill_if_stopped, 'interval', seconds=10)

                try:
                    p.wait()
                finally:
                    log_reprinter.stop()
                    save_metrics(metrics_path)
                    sched.shutdown()
                    db.checkpoint_experiment(experiment)
                    db.finish_experiment(experiment)
                    return p.returncode


def allocate_resources(experiment, config=None, verbose=10):
    logger = logs.getLogger('allocate_resources')
    logger.setLevel(verbose)
    logger.info('Allocating resources {} for experiment {}'
                .format(experiment.resources_needed, experiment.key))

    ret_val = True
    gpus_needed = int(experiment.resources_needed.get('gpus')) \
        if experiment.resources_needed else 0

    if gpus_needed > 0:
        ret_val = ret_val and allocate_gpus(gpus_needed,
                                            experiment.resources_needed,
                                            config)
    else:
        allocate_gpus(0)

    return ret_val


def allocate_gpus(gpus_needed, resources_needed={}, config=None):
    # Only disable gpus if gpus_needed < 0
    if gpus_needed < 0:
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        return True
    elif gpus_needed == 0:
        return True

    gpu_mem_needed = resources_needed.get('gpuMem', None)
    strict = resources_needed.get('gpuMemStrict', False)

    available_gpus = get_available_gpus(gpu_mem_needed, strict)
    gpu_mapping = get_gpu_mapping()
    mapped_gpus = [str(gpu_mapping[g]) for g in available_gpus]

    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
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
    parser.add_argument(
        '--verbose',
        default='error')

    # Register signal handler for signal.SIGUSR1
    # which will invoke built-in Python debugger:
    signal.signal(signal.SIGUSR1, lambda sig, stack: pdb.set_trace())

    parsed_args, script_args = parser.parse_known_args(args)
    verbose = parse_verbosity(parsed_args.verbose)

    queue = LocalQueue(verbose=verbose)
    # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")
    # wait_for_messages(queue, parsed_args.timeout)
    returncode = worker_loop(queue, parsed_args, timeout=parsed_args.timeout)
    sys.exit(returncode)


def which(program):
    import os

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def worker_loop(queue, parsed_args,
                single_experiment=False,
                timeout=0,
                verbose=None):

    fetch_artifacts = True

    logger = logs.getLogger('worker_loop')

    hold_period = 4
    retval = 0
    while True:
        msg = queue.dequeue(acknowledge=False, timeout=timeout)
        if not msg:
            break

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

        logger.debug('Received message: \n{}'.format(data_dict))

        executor = LocalExecutor(queue, parsed_args)

        with model.get_db_provider(config) as db:
            # experiment = experiment_from_dict(data_dict['experiment'])
            def try_get_experiment():
                experiment = db.get_experiment(experiment_key)
                if experiment is None:
                    raise ValueError(
                        'experiment is not found - indicates storage failure')
                return experiment

            experiment = retry(
                try_get_experiment,
                sleep_time=10,
                logger=logger)

            if config.get('experimentLifetime') and \
                int(str2duration(config['experimentLifetime'])
                    .total_seconds()) + experiment.time_added < time.time():
                logger.info(
                    'Experiment expired (max lifetime of {0} was exceeded)'
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
                    if experiment.pythonver[0] == '3':
                        python = 'python3'
                    if '_singularity' not in experiment.artifacts.keys():
                        pip_diff = pip_needed_packages(
                            experiment.pythonenv, python)
                        if any(pip_diff):
                            logger.info(
                                'Setting up python packages for experiment')
                            if pip_install_packages(
                                    pip_diff,
                                    python,
                                    logger
                            ) != 0:

                                logger.info(
                                    "Installation of all packages together " +
                                    " failed, "
                                    "trying one package at a time")

                                for pkg in pip_diff:
                                    pip_install_packages([pkg], python, logger)

                    for tag, item in experiment.artifacts.items():
                        art: Artifact = item
                        if fetch_artifacts or art.local_path is None:
                            get_only_newer: bool = True
                            if tag == 'workspace':
                                get_only_newer = False

                            if not art.is_mutable:
                                logger.info('Fetching artifact ' + tag)
                                art.local_path = retry(
                                    lambda: db.get_artifact(art, only_newer=get_only_newer),
                                    sleep_time=10,
                                    logger=logger
                                )
                            else:
                                logger.info('Skipping mutable artifact ' + tag)


                    returncode = executor.run(experiment)
                    if returncode != 0:
                        retval = returncode
                finally:
                    sched.shutdown()
                    queue.acknowledge(ack_key)

                if single_experiment:
                    logger.info('single_experiment is True, quitting')
                    return retval
            else:
                logger.info('Cannot run experiment ' + experiment.key +
                            ' due lack of resources. Will retry')
                # Debounce failed requests we cannot service yet
                time.sleep(config.get('sleep_time', 5))

    logger.info("Queue in {0} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))

    return retval


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
