import sys
import argparse
import logging
import json
import re
import os
import uuid
import shutil

from local_queue import LocalQueue
from pubsub_queue import PubsubQueue
from gcloud_worker import GCloudWorkerManager
from ec2cloud_worker import EC2WorkerManager

import model
import auth
import git_util
import local_worker
import fs_tracker


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
        '--experiment', '-e',
        help='name of the experiment. If none provided, ' +
             'random uuid will be generated',
        default=None)

    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parser.add_argument(
        '--force-git',
        help='If run in a git directory, force running the experiment ' +
             'even if changes are not commited',
        action='store_true')

    parser.add_argument(
        '--gpus',
        help='Number of gpus needed to run the experiment',
        default=None)

    parser.add_argument(
        '--cpus',
        help='Number of cpus needed to run the experiment' +
             ' (used to configure cloud instance)',
        default=None)

    parser.add_argument(
        '--ram',
        help='Amount of RAM needed to run the experiment' +
             ' (used to configure cloud instance)',
        default=None)

    parser.add_argument(
        '--hdd',
        help='Amount of hard drive space needed to run the experiment' +
             ' (used to configure cloud instance)',
        default=None)

    parser.add_argument(
        '--queue', '-q',
        help='Name of the remote execution queue',
        default=None)

    parser.add_argument(
        '--cloud',
        help='Cloud execution mode',
        default=None)

    parser.add_argument(
        '--capture-once', '-co',
        help='Name of the immutable artifact to be captured. ' +
        'It will be captured once before the experiment is run',
        default=[], action='append')

    parser.add_argument(
        '--capture', '-c',
        help='Name of the mutable artifact to be captured continously',
        default=[], action='append')

    parser.add_argument(
        '--reuse', '-r',
        help='Name of the artifact from another experiment to use',
        default=[], action='append')

    parser.add_argument(
        '--verbose', '-v',
        help='Verbosity level. Allowed vaules: ' +
             'debug, info, warn, error, crit ' +
             'or numerical value of logger levels.',
        default=None)

    parser.add_argument(
        '--metric', '-m',
        help='Metric to show in the summary of the experiment, ' +
             'and to base hyperparameter search on. ' +
             'Refers a scalar value in tensorboard log ' + 
             'example: --metric=val_loss[:final | :min | :max] to report ' +
             'validation loss in the end of the keras experiment ' +
             '(or smallest or largest throughout the experiment for :min and :max ' +
             'respectively)',
        default=None)

    parser.add_argument(
        '--hyperparam',
        help='Try out multiple values of a certain parameter. ' +
             'For example, --hyperparam=learning_rate:0.01:0.1:l10 ' + 
             'will instantiate 10 versions of the script, replace learning_rate ' +
             'with a one of the 10 values for learning rate that lies ' + 
             'on a log grid from 0.01 to 0.1, create experiments and place ' + 
             'them in the queue. For local or a cloud execution number of workers ' +
             'can be controlled by --num-workers option',
        default=[], action='append')

        

    parsed_args, script_args = parser.parse_known_args(args)

    exec_filename, other_args = script_args[1], script_args[2:]
    # TODO: Queue the job based on arguments and only then execute.

    config = model.get_config(parsed_args.config)

    if parsed_args.verbose:
        config['verbose'] = parsed_args.verbose

    verbose = model.parse_verbosity(config['verbose'])
    logger.setLevel(verbose)

    db = model.get_db_provider(config)

    if git_util.is_git() and not git_util.is_clean():
        logger.warn('Running from dirty git repo')
        if not parsed_args.force_git:
            logger.error(
                'Specify --force-git to run experiment from dirty git repo')
            sys.exit(1)

    resources_needed = parse_hardware(parsed_args, config['cloud'])
    logger.debug('resources requested: ')
    logger.debug(str(resources_needed))

    artifacts = {}
    artifacts.update(parse_artifacts(parsed_args.capture, mutable=True))
    artifacts.update(parse_artifacts(parsed_args.capture_once, mutable=False))
    artifacts.update(parse_external_artifacts(parsed_args.reuse, db))

    if any(parsed_args.hyperparam):
        experiments = add_hyperparam_experiments(
                exec_filename, 
                other_args,
                parsed_args,
                artifacts, 
                resources_needed) 
    else:
        experiments = [model.create_experiment(
            filename=exec_filename,
            args=other_args,
            experiment_name=parsed_args.experiment,
            project=parsed_args.project,
            artifacts=artifacts,
            resources_needed=resources_needed,
            metric=parsed_args.metric)]


    for e in experiments:
        db.add_experiment(e)
        logger.info("Added experiment " + e.key)


    if parsed_args.cloud is not None:
        assert parsed_args.cloud == 'gcloud' or 'ec2', \
            'Only gcloud or ec2 are supported for now'
        if parsed_args.cloud == 'gcloud':
            if parsed_args.queue is None:
                parsed_args.queue = 'gcloud_' + str(uuid.uuid4())

            if not parsed_args.queue.startswith('gcloud_'):
                parsed_args.queue = 'gcloud_' + parsed_args.queue

        if parsed_args.cloud == 'ec2':
            if parsed_args.queue is None:
                parsed_args.queue = 'ec2_' + str(uuid.uuid4())

            if not parsed_args.queue.startswith('ec2_'):
                parsed_args.queue = 'ec2_' + parsed_args.queue

    queue = LocalQueue() if not parsed_args.queue else \
        PubsubQueue(parsed_args.queue, verbose=verbose)


    for e in experiments:
        queue.enqueue(json.dumps({
            'experiment': e.key,
            'config': config}))

    if not parsed_args.queue:
        worker_args = ['studio-local-worker']

        if parsed_args.config:
            worker_args += ['--config=' + parsed_args.config]
        if parsed_args.guest:
            worker_args += ['--guest']

        logger.info('worker args: {}'.format(worker_args))
        local_worker.main(worker_args)
    elif parsed_args.queue.startswith('gcloud_') or \
            parsed_args.queue.startswith('ec2_'):

        auth_cookie = None if config['database'].get('guest') \
            else os.path.join(
            auth.token_dir,
            config['database']['apiKey']
        )

        if parsed_args.queue.startswith('gcloud_'):
            worker_manager = GCloudWorkerManager(
                auth_cookie=auth_cookie,
                zone=config['cloud']['zone']
            )
        else:
            worker_manager = EC2WorkerManager(
                auth_cookie=auth_cookie
            )
        worker_manager.start_worker(parsed_args.queue, resources_needed)

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


def parse_hardware(parsed_args, config={}):
    resources_needed = {}
    parse_list = ['gpus', 'cpus', 'ram', 'hdd']
    for key in parse_list:
        from_args = parsed_args.__dict__.get(key)
        from_config = config.get(key)
        if from_args is not None:
            resources_needed[key] = from_args
        elif from_config is not None:
            resources_needed[key] = from_config

    return resources_needed


def add_hyperparam_experiments(exec_filename, other_args, parsed_args, artifacts, resources_needed):

    project = parsed_args.project if parsed_args.project else \
            'hyperparam' + str(uuid.uuid4())

    experiment_name_base = parsed_args.experiment if parsed_args.experiment \
                          else str(uuid.uuid4())
                      
    experiments = [] 
    for hyperparam in parsed_args.hyperparam:
        param_name = hyperparam.split(':')[0]
        param_value = float(hyperparam.split(':')[1])

        experiment_name = experiment_name_base + '__' + param_name + '__' + str(param_value)
        experiment_name = experiment_name.replace('.','_')
    
        workspace_orig = artifacts['workspace']['local'] if 'workspace' in artifacts.keys() \
                else '.'
        workspace_new = fs_tracker.get_artifact_cache('workspace', experiment_name) 
        
        current_artifacts = artifacts.copy()
        current_artifacts.update({
                'workspace': {
                        'local': workspace_new,
                        'mutable':True 
                    }
                })
    
        shutil.copytree(workspace_orig, workspace_new)

        
        # replace hyperparameter with new value

        experiments.append(model.create_experiment(
            filename=exec_filename,
            args=other_args,
            experiment_name=experiment_name,
            project=project,
            artifacts=current_artifacts,
            resources_needed=resources_needed,
            metric=parsed_args.metric))

    return experiments
   

if __name__ == "__main__":
    main()
