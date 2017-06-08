
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

def main(args=sys.argv):
    logger = logging.getLogger('studio-runner')
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
    
    parser.add_argument(
        '--gpus',
        help='Number of gpus needed to run the experiment',
        type=int, default=0)

    parsed_args, script_args = parser.parse_known_args(args)
    exec_filename, other_args = script_args[1], script_args[2:]
    # TODO: Queue the job based on arguments and only then execute.

    resources_needed = None
    if parsed_args.gpus > 0:
        resources_needed = {}
        resources_needed['gpus'] = parsed_args.gpus; 

    experiment = model.create_experiment(
            filename=exec_filename,
            args=other_args,
            experiment_name=parsed_args.experiment,
            project=parsed_args.project,
            resources_needed=resources_needed)

    logger.info("Experiment name: " + experiment.key)
    db = model.get_db_provider(model.get_config(parsed_args.config))
    db.add_experiment(experiment)
    
    with open(os.path.join(
        fs_tracker.get_queue_directory(),
        experiment.key), 'w') as f:
            f.write('queued')
    worker_args = ['studio-lworker']

    if parsed_args.config:
        worker_args += '--config=' + parsed_args.config
    if parsed_args.guest:
        worker_args += '--guest'

    worker = subprocess.Popen(worker_args)
    worker.wait()
 

if __name__ == "__main__":
    main()
