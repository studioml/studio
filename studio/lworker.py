import os
import sys
import subprocess
import argparse
import yaml
import logging
import glob

from apscheduler.schedulers.background import BackgroundScheduler

import fs_tracker
import model

logging.basicConfig()


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.
    """

    def __init__(self, args):
        self.config = model.get_config()
        if args.config:
            with open(args.config) as f:
                self.config.update(yaml.load(f))

        if args.guest:
            self.config['database']['guest'] = True

        self.db = model.get_db_provider(self.config)
        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(10)
        self.logger.debug("Config: ")
        self.logger.debug(self.config)

    def run(self, experiment_key):
        experiment = self.db.get_experiment(experiment_key)
        self.logger.info("Experiment key: " + experiment.key)

        self.db.start_experiment(experiment)

        env = os.environ.copy()
        fs_tracker.setup_model_directory(env, experiment.key)
        model_dir = fs_tracker.get_model_directory(experiment.key)
        log_path = os.path.join(model_dir, self.config['log']['name'])

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


def main(args=sys.argv):
    logger = logging.getLogger('studio-lworker')
    logger.setLevel(10)
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio worker. \
                     Usage: studio-worker \
                     ')
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument( 
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parsed_args, script_args = parser.parse_known_args(args)

    executor = LocalExecutor(parsed_args)

    queue = glob.glob(fs_tracker.get_queue_directory() + "/*")
    while any(queue):
        first_exp = min([(p, os.path.getmtime(p)) for p in queue], 
                        key=lambda t: t[1])[0]
        
        os.remove(first_exp)
        executor.run(os.path.basename(first_exp))

        queue = glob.glob(fs_tracker.get_queue_directory() + "/*")

    logger.info("Queue in {} is empty, quitting"
                .format(fs_tracker.get_queue_directory()))


if __name__ == "__main__":
    main()
