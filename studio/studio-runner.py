#!/usr/bin/python

import os
import sys
import subprocess
import argparse
import yaml
import hashlib
import logging
logging.basicConfig()

from apscheduler.schedulers.background import BackgroundScheduler
from configparser import ConfigParser

import fs_tracker
import model


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.

    TODO: capturing state and results.
    """

    def __init__(self, config_file=None):
        self.config = model.get_default_config()
        if config_file:
            with open(config_file) as f:
                self.config.update(yaml.load(f))

        self.db = model.get_db_provider(self.config)
        self.sched = BackgroundScheduler()
        self.sched.start()
        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(10)

    def run(self, filename, args):
        experiment = model.create_experiment(
            filename=filename, args=args)
        self.logger.info("Experiment name: " + experiment.key)

        keyBase = 'experiments/' + experiment.key + '/'
        self.db.add_experiment(experiment)
        self.save_dir(".", keyBase + "workspace/")

        env = os.environ.copy()
        fs_tracker.setup_model_directory(env, experiment.key)
        model_dir = fs_tracker.get_model_directory(experiment.key)
        log_path = os.path.join(model_dir, self.config['log']['name'])

        with open(log_path, 'w') as output_file:
            p = subprocess.Popen(["python", filename] + args, stdout=output_file, stderr=subprocess.STDOUT, env=env)
            ptail = subprocess.Popen(["tail", "-f", log_path]) # simple hack to show what's in the log file

            self.sched.add_job(lambda: self.save_dir(model_dir, keyBase + "modeldir/"), 'interval', minutes = self.config['saveWorkspaceFrequency'])
            self.sched.add_job(lambda: self.save_dir(".", keyBase + "workspace_latest/"), 'interval', minutes = self.config['saveWorkspaceFrequency'])

            p.wait()
            ptail.kill()

    def save_dir(self, localFolder, keyBase):
        self.logger.debug("saving workspace to keyBase = " + keyBase)
        for root, dirs, files in os.walk(localFolder, topdown=False):
            for name in files:
                fullFileName = os.path.join(root, name)
                self.logger.debug("Saving " + fullFileName)
                with open(fullFileName) as f:
                    data = f.read()
                    sha = hashlib.sha256(data).hexdigest()
                    self.db[keyBase + sha + "/data"] = data
                    self.db[keyBase + sha + "/name"] = name

        self.logger.debug("Done saving")

    def __del__(self):
        self.sched.shutdown()


def main(args):
    exec_filename, other_args = args.script_args[0], args.script_args[1:]
    # TODO: Queue the job based on arguments and only then execute.
    LocalExecutor(args.config).run(exec_filename, other_args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TensorFlow Studio runner. Usage: studio-runner script <script_arguments>')
    parser.add_argument('script_args', metavar='N', type=str, nargs='+')
    parser.add_argument('--config', '-c', help='configuration file')

    args = parser.parse_args()
    main(args)
