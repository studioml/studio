import os
import sys
import subprocess
import argparse
import yaml
import logging
import time
import xml.etree.ElementTree as ET
import json

from apscheduler.schedulers.background import BackgroundScheduler

import fs_tracker
import model
from local_queue import LocalQueue

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
        fs_tracker.setup_model_directory(env, experiment.key)
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
    if config and 'cudaDeviceMapping' in config.keys():
        mapped_gpus = [str(config['cudaDeviceMapping'][g])
                       for g in available_gpus]
    else:
        mapped_gpus = [str(g) for g in available_gpus]

    if len(mapped_gpus) >= gpus_needed:
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(
            mapped_gpus[:gpus_needed])
        return True
    else:
        return False


def get_available_gpus():
    try:
        smi_proc = subprocess.Popen(['nvidia-smi', '-q', '-x'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

        smi_output, _ = smi_proc.communicate()
        xmlroot = ET.fromstring(smi_output)
    except Exception:
        return []

    def check_gpu(gpuinfo):
        return memstr2int(gpu.find('fb_memory_usage').find('used').text) < \
            0.1 * memstr2int(gpu.find('fb_memory_usage').find('total').text)

    return [gpu.find('minor_number').text
            for gpu in xmlroot.findall('gpu') if check_gpu(gpu)]


def memstr2int(string):
    conversion_factors = [('Mb', 2**20), ('MiB', 2**20),
                          ('Gb', 2**30), ('GiB', 2**30),
                          ('kb', 2**10)]

    for k, f in conversion_factors:
        if string.endswith(k):
            return int(string.replace(k, '')) * f

    return int(string)


def main(args=sys.argv):
    logger = logging.getLogger('studio-lworker')
    logger.setLevel(10)
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio worker. \
                     Usage: studio-lworker \
                     ')

    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parsed_args, script_args = parser.parse_known_args(args)

    queue = LocalQueue()
    # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

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
            executor.run(experiment)
        else:
            logger.info('Cannot run experiment ' + experiment.key +
                        ' due lack of resources. Will retry')
            time.sleep(5)

        # queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    logger.info("Queue in {} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))


if __name__ == "__main__":
    main()
