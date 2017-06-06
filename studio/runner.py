
import os
import sys
import subprocess
import argparse
import yaml
import logging

from apscheduler.schedulers.background import BackgroundScheduler

import fs_tracker
import model

logging.basicConfig()


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.

    TODO: capturing state and results.
    """

    def __init__(self, args):
        self.config = model.get_default_config()
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

    def run(self, filename, args, experiment_name=None, project=None):
        experiment = model.create_experiment(
            filename=filename,
            args=args,
            experiment_name=experiment_name,
            project=project)
        self.logger.info("Experiment name: " + experiment.key)

        self.db.add_experiment(experiment)
        self.db.start_experiment(experiment)

        env = os.environ.copy()
        fs_tracker.setup_model_directory(env, experiment.key)
        model_dir = fs_tracker.get_model_directory(experiment.key)
        log_path = os.path.join(model_dir, self.config['log']['name'])

        sched = BackgroundScheduler()
        sched.start()

        with open(log_path, 'w') as output_file:
            p = subprocess.Popen(["python",
                                  filename] + args,
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
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio runner. \
                     Usage: studio-runner \
                     script <script_arguments>')
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument('--project', help='name of the project', default=None)
    parser.add_argument(
        '--experiment',
        help='name of the experiment. If none provided, ' +
             'random uuid will be generated',
        default=None)
    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parsed_args, script_args = parser.parse_known_args(args)
    exec_filename, other_args = script_args[1], script_args[2:]
    # TODO: Queue the job based on arguments and only then execute.
    LocalExecutor(parsed_args).run(
        exec_filename,
        other_args,
        experiment_name=parsed_args.experiment,
        project=parsed_args.project)


if __name__ == "__main__":
    main()
