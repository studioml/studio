import sys
import subprocess
import argparse
import logging
import json
import re
import os

import model
from local_queue import LocalQueue
from pubsub_queue import PubsubQueue

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
        '--experiment','-e',
        help='name of the experiment. If none provided, ' +
             'random uuid will be generated',
        default=None)

    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parser.add_argument(
        '--gpus','-g',
        help='Number of gpus needed to run the experiment',
        type=int, default=0)

    parser.add_argument(
        '--queue','-q',
        help='Name of the remote execution queue',
        default=None)

    parser.add_argument(
        '--capture-once','-co'
        help='Name of the immutable artifact to be captured. ' +
        'It will be captured once before the experiment is run',
        default=[], action='append')

    parser.add_argument(
        '--capture-once','-c'
        help='Name of the mutable artifact to be captured continously',
        default=[], action='append')

    parser.add_argument(
        '--reuse','-r'
        help='Name of the artifact from another experiment to use',
        default=[], action='append')

    parsed_args, script_args = parser.parse_known_args(args)

    exec_filename, other_args = script_args[1], script_args[2:]
    # TODO: Queue the job based on arguments and only then execute.

    resources_needed = None
    if parsed_args.gpus > 0:
        resources_needed = {}
        resources_needed['gpus'] = parsed_args.gpus

    config = model.get_config(parsed_args.config)
    db = model.get_db_provider(config)

    artifacts = {}
    artifacts.update(parse_artifacts(parsed_args.capture, mutable=True))
    artifacts.update(parse_artifacts(parsed_args.capture_once, mutable=False))
    artifacts.update(parse_external_artifacts(parsed_args.reuse, db))

    experiment = model.create_experiment(
        filename=exec_filename,
        args=other_args,
        experiment_name=parsed_args.experiment,
        project=parsed_args.project,
        artifacts=artifacts,
        resources_needed=resources_needed)

    logger.info("Experiment name: " + experiment.key)
    db.add_experiment(experiment)

    queue = LocalQueue() if not parsed_args.queue else \
        PubsubQueue(parsed_args.queue)

    queue.enqueue(json.dumps({
        'experiment': experiment.key,
        'config': config}))

    if not parsed_args.queue:
        worker_args = ['studio-local-worker']

        if parsed_args.config:
            worker_args += '--config=' + parsed_args.config
        if parsed_args.guest:
            worker_args += '--guest'

        logger.info('worker args: {}'.format(worker_args))
        worker = subprocess.Popen(worker_args)
        worker.wait()

    db = None


def parse_artifacts(art_list, mutable):
    retval = {}
    for entry in art_list:
        path = re.sub(':.*', '', entry)
        tag = re.sub('.*:', '', entry)
        retval[tag] = {
            'local': os.path.expanduser(path),
            'mutable': mutable
        }
    return retval


def parse_external_artifacts(art_list, db):
    retval = {}
    for entry in art_list:
        external = re.sub(':.*', '', entry)
        tag = re.sub('.*:', '', entry)

        experiment_key = re.sub('/.*', '', external)
        external_tag = re.sub('.*/', '', external)
        experiment = db.get_experiment(experiment_key, getinfo=False)

        retval[tag] = {
            'key': experiment.artifacts[external_tag]['key'],
            'mutable': False
        }
    return retval


if __name__ == "__main__":
    main()
