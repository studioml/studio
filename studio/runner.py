
import os
import sys
import subprocess
import argparse
import yaml
import hashlib
import base64
import logging
import zlib
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
        self.logger = logging.getLogger('LocalExecutor')
        self.logger.setLevel(10)
        self.logger.debug("Config: ")
        self.logger.debug(self.config)

    def run(self, filename, args, experiment_name = None,  save_workspace = True):
        experiment = model.create_experiment(
            filename=filename, args=args, experiment_name = experiment_name)
        self.logger.info("Experiment name: " + experiment.key)

        key_base = 'experiments/' + experiment.key + '/'
        self.db.add_experiment(experiment)

        env = os.environ.copy()
        fs_tracker.setup_model_directory(env, experiment.key)
        model_dir = fs_tracker.get_model_directory(experiment.key)
        log_path = os.path.join(model_dir, self.config['log']['name'])

        def save_workspace(keySuffix='workspace_latest/'):
            if save_workspace:
                self.save_dir('.', key_base + keySuffix)

        def save_modeldir():
            self.save_dir(model_dir, key_base + "modeldir/")
        
        save_workspace('workspace/')
        sched = BackgroundScheduler()
        sched.start()



        with open(log_path, 'w') as output_file:
            p = subprocess.Popen(["python", filename] + args, stdout=output_file, stderr=subprocess.STDOUT, env=env)
            ptail = subprocess.Popen(["tail", "-f", log_path]) # simple hack to show what's in the log file

            sched.add_job(save_modeldir,  'interval', minutes = self.config['saveWorkspaceFrequency'])
            sched.add_job(save_workspace, 'interval', minutes = self.config['saveWorkspaceFrequency'])
            
            try:
                p.wait()
            finally:
                ptail.kill()

                self.save_dir(model_dir, key_base + 'modeldir/')
                save_workspace()
                sched.shutdown()
                
       
    def save_dir(self, localFolder, key_base):
        self.logger.debug("saving workspace to key_base = " + key_base)
        for root, dirs, files in os.walk(localFolder, topdown=False):
            for name in files:
                fullFileName = os.path.join(root, name)
                self.logger.debug("Saving " + fullFileName)
                with open(fullFileName, 'rb') as f:
                    data = f.read()
                    sha = hashlib.sha256(data).hexdigest()
                    self.db[key_base + sha + "/data"] = base64.b64encode(zlib.compress(bytes(data)))
                    self.db[key_base + sha + "/name"] = name

        self.logger.debug("Done saving")

def main(args=sys.argv):
    parser = argparse.ArgumentParser(description='TensorFlow Studio runner. Usage: studio-runner script <script_arguments>')
    parser.add_argument('script_args', metavar='N', type=str, nargs='+')
    parser.add_argument('--config', '-c', help='configuration file')

    parsed_args = parser.parse_args(args)
    exec_filename, other_args = parsed_args.script_args[1], parsed_args.script_args[2:]
    # TODO: Queue the job based on arguments and only then execute.
    LocalExecutor(parsed_args.config).run(exec_filename, other_args)
    
if __name__ == "__main__":
    main()
