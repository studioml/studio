import sys
import argparse
import logging
import json
import re
import os
import uuid
import shutil
import importlib
import time
import multiprocessing
import traceback
from contextlib import closing

import numpy as np

from local_queue import LocalQueue
from pubsub_queue import PubsubQueue
from sqs_queue import SQSQueue
from gcloud_worker import GCloudWorkerManager
from ec2cloud_worker import EC2WorkerManager
from hyperparameter import HyperparameterParser
from util import rand_string, Progbar, rsync_cp

import model
import auth
import git_util
import local_worker
import fs_tracker


logging.basicConfig()


def main(args=sys.argv):
    logger = logging.getLogger('studio-runner')
    parser = argparse.ArgumentParser(
        description='Studio runner. \
                     Usage: studio run <runner_arguments> \
                     script <script_arguments>')
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument('--project', help='name of the project', default=None)
    parser.add_argument(
        '--experiment', '-e',
        help='Name of the experiment. If none provided, ' +
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
        type=int,
        default=None)

    parser.add_argument(
        '--cpus',
        help='Number of cpus needed to run the experiment' +
             ' (used to configure cloud instance)',
        type=int,
        default=None)

    parser.add_argument(
        '--ram',
        help='Amount of RAM needed to run the experiment' +
             ' (used to configure cloud instance), ex: 10G, 10GB',
        default=None)

    parser.add_argument(
        '--hdd',
        help='Amount of hard drive space needed to run the experiment' +
             ' (used to configure cloud instance), ex: 10G, 10GB',
        default=None)

    parser.add_argument(
        '--queue', '-q',
        help='Name of the remote execution queue',
        default=None)

    parser.add_argument(
        '--cloud',
        help='Cloud execution mode. Could be gcloud, gcspot, ec2 or ec2spot',
        default=None)

    parser.add_argument(
        '--bid',
        help='Spot instance price bid, specified in USD or in percentage ' +
             'of on-demand instance price. Default is %(default)s',
        default='100%')

    parser.add_argument(
        '--capture-once', '-co',
        help='Name of the immutable artifact to be captured. ' +
        'It will be captured once before the experiment is run',
        default=[], action='append')

    parser.add_argument(
        '--capture', '-c',
        help='Name of the mutable artifact to be captured continuously',
        default=[], action='append')

    parser.add_argument(
        '--reuse', '-r',
        help='Name of the artifact from another experiment to use',
        default=[], action='append')

    parser.add_argument(
        '--verbose', '-v',
        help='Verbosity level. Allowed values: ' +
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
             '(or smallest or largest throughout the experiment for :min ' +
             'and :max respectively)',
        default=None)

    parser.add_argument(
        '--hyperparam', '-hp',
        help='Try out multiple values of a certain parameter. ' +
             'For example, --hyperparam=learning_rate:0.01:0.1:l10 ' +
             'will instantiate 10 versions of the script, replace ' +
             'learning_rate with a one of the 10 values for learning ' +
             'rate that lies on a log grid from 0.01 to 0.1, create '
             'experiments and place them in the queue.',
             default=[], action='append')

    parser.add_argument(
        '--num-workers',
        help='Number of local or cloud workers to spin up',
        type=int,
        default=None)

    parser.add_argument(
        '--python-pkg',
        help='Python package not present in the current environment ' +
             'that is needed for experiment. Only compatible with ' +
             'remote and cloud workers for now',
        default=[], action='append')

    parser.add_argument(
        '--ssh-keypair',
        help='Name of the SSH keypair used to access the EC2 ' +
             'instances directly',
        default=None)

    parser.add_argument(
        '--optimizer', '-opt',
        help='Name of optimizer to use, by default is grid search. ' +
        'The name of the optimizer must either be in ' +
        'studio/optimizer_plugins ' +
        'directory or the path to the optimizer source file ' +
        'must be supplied. ',
        default='grid')

    parser.add_argument(
        '--cloud-timeout',
        help="Time (in seconds) that cloud workers wait for messages. " +
             "If negative, " +
             "wait for the first message in the queue indefinitely " +
             "and shut down " +
             "as soon as no new messages are available. " +
             "If zero, don't wait at all." +
             "Default value is %(default)d",
        type=int,
        default=300)

    parser.add_argument(
        '--user-startup-script',
        help='Path of script to run before running the remote worker',
        default=None)

    parser.add_argument(
        '--branch',
        help='Branch of studioml to use when running remote worker, useful ' +
             'for debugging pull requests',
        default='master')

    # detect which argument is the script filename
    # and attribute all arguments past that index as related to the script
    py_suffix_args = [i for i, arg in enumerate(args) if arg.endswith('.py')]
    if len(py_suffix_args) < 1:
        print('At least one argument should be a python script ' +
              '(end with *.py)')
        parser.print_help()
        exit()

    script_index = py_suffix_args[0]
    runner_args = parser.parse_args(args[1:script_index])

    exec_filename, other_args = args[script_index], args[script_index + 1:]
    # TODO: Queue the job based on arguments and only then execute.

    config = model.get_config(runner_args.config)

    if runner_args.verbose:
        config['verbose'] = runner_args.verbose

    if runner_args.guest:
        config['database']['guest'] = True

    verbose = model.parse_verbosity(config['verbose'])
    logger.setLevel(verbose)

    if git_util.is_git() and not git_util.is_clean():
        logger.warn('Running from dirty git repo')
        if not runner_args.force_git:
            logger.error(
                'Specify --force-git to run experiment from dirty git repo')
            sys.exit(1)

    resources_needed = parse_hardware(runner_args, config['cloud'])
    logger.debug('resources requested: ')
    logger.debug(str(resources_needed))

    artifacts = {}
    artifacts.update(parse_artifacts(runner_args.capture, mutable=True))
    artifacts.update(parse_artifacts(runner_args.capture_once, mutable=False))
    with model.get_db_provider(config) as db:
        artifacts.update(parse_external_artifacts(runner_args.reuse, db))

    if any(runner_args.hyperparam):
        if runner_args.optimizer is "grid":
            experiments = add_hyperparam_experiments(
                exec_filename,
                other_args,
                runner_args,
                artifacts,
                resources_needed,
                logger)
            submit_experiments(
                experiments,
                resources_needed,
                config,
                runner_args,
                logger,
                resources_needed)
        else:
            opt_modulepath = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "optimizer_plugins",
                runner_args.optimizer + ".py")
            if not os.path.exists(opt_modulepath):
                opt_modulepath = os.path.abspath(
                    os.path.expanduser(runner_args.optimizer))
            logger.info('optimizer path: %s' % opt_modulepath)

            assert os.path.exists(opt_modulepath)
            sys.path.append(os.path.dirname(opt_modulepath))
            opt_module = importlib.import_module(
                os.path.basename(opt_modulepath.replace(".py", '')))

            h = HyperparameterParser(runner_args, logger)
            hyperparams = h.parse()
            optimizer = getattr(
                opt_module,
                "Optimizer")(
                hyperparams,
                config['optimizer'],
                logger)

            queue_name = None
            while not optimizer.stop():
                hyperparam_pop = optimizer.ask()
                hyperparam_tuples = h.convert_to_tuples(hyperparam_pop)

                experiments = add_hyperparam_experiments(
                    exec_filename,
                    other_args,
                    runner_args,
                    artifacts,
                    resources_needed,
                    logger,
                    optimizer=optimizer,
                    hyperparam_tuples=hyperparam_tuples)
                queue_name = submit_experiments(
                    experiments,
                    resources_needed,
                    config,
                    runner_args,
                    logger,
                    queue_name,
                    queue_name is None)

                fitnesses = get_experiment_fitnesses(experiments,
                                                     optimizer, config, logger)

                # for i, hh in enumerate(hyperparam_pop):
                #     print fitnesses[i]
                #     for hhh in hh:
                #         print hhh
                optimizer.tell(hyperparam_pop, fitnesses)
                try:
                    optimizer.disp()
                except BaseException:
                    logger.warn('Optimizer has no disp() method')
    else:
        experiments = [model.create_experiment(
            filename=exec_filename,
            args=other_args,
            experiment_name=runner_args.experiment,
            project=runner_args.project,
            artifacts=artifacts,
            resources_needed=resources_needed,
            metric=runner_args.metric)]
        submit_experiments(experiments,
                           resources_needed,
                           config,
                           runner_args,
                           logger)

    return


def add_experiment(args):
    try:
        config, python_pkg, e = args
        e.pythonenv = add_packages(e.pythonenv, python_pkg)
        with model.get_db_provider(config) as db:
            db.add_experiment(e)
    except BaseException:
        traceback.print_exc()
        raise
    return e


def submit_experiments(
        experiments,
        resources_needed,
        config,
        runner_args,
        logger,
        queue_name=None,
        launch_workers=True):

    num_experiments = len(experiments)
    verbose = model.parse_verbosity(config['verbose'])

    if runner_args.cloud is None:
        queue_name = 'local'
        if 'queue' in config.keys():
            queue_name = config['queue']
        if runner_args.queue:
            queue_name = runner_args.queue

    start_time = time.time()
    n_workers = min(multiprocessing.cpu_count() * 2, num_experiments)
    with closing(multiprocessing.Pool(n_workers, maxtasksperchild=20)) as p:
        experiments = p.imap_unordered(add_experiment,
                                       zip([config] * num_experiments,
                                           [runner_args.python_pkg] *
                                           num_experiments,
                                           experiments),
                                       chunksize=1)
        p.close()
        p.join()
    # for e in experiments:
    #     logger.info("Added experiment " + e.key)
    logger.info("Added %s experiments in %s seconds" %
                (num_experiments, int(time.time() - start_time)))

    if runner_args.cloud is not None:
        assert runner_args.cloud in ['gcloud', 'gcspot', 'ec2', 'ec2spot']

        assert runner_args.queue is None, \
            '--queue argument cannot be provided with --cloud argument'
        auth_cookie = None if config['database'].get('guest') \
            else os.path.join(
            auth.TOKEN_DIR,
            config['database']['apiKey']
        )

        if runner_args.cloud in ['gcloud', 'gcspot']:
            if queue_name is None:
                queue_name = 'pubsub_' + str(uuid.uuid4())
                worker_manager = GCloudWorkerManager(
                    runner_args=runner_args,
                    auth_cookie=auth_cookie,
                    zone=config['cloud']['zone']
                )

            queue = PubsubQueue(queue_name, verbose=verbose)

        if runner_args.cloud in ['ec2', 'ec2spot']:
            if queue_name is None:
                queue_name = 'sqs_' + str(uuid.uuid4())
                worker_manager = EC2WorkerManager(
                    runner_args=runner_args,
                    auth_cookie=auth_cookie
                )

            queue = SQSQueue(queue_name, verbose=verbose)

        if launch_workers:
            if runner_args.cloud == 'gcloud' or \
               runner_args.cloud == 'ec2':

                num_workers = int(
                    runner_args.num_workers) if runner_args.num_workers else 1
                for i in range(num_workers):
                    worker_manager.start_worker(
                        queue_name, resources_needed,
                        ssh_keypair=runner_args.ssh_keypair,
                        timeout=runner_args.cloud_timeout)
            else:
                assert runner_args.bid is not None
                if runner_args.num_workers:
                    start_workers = runner_args.num_workers
                    queue_upscaling = False
                else:
                    start_workers = 1
                    queue_upscaling = True

                worker_manager.start_spot_workers(
                    queue_name,
                    runner_args.bid,
                    resources_needed,
                    start_workers=start_workers,
                    queue_upscaling=queue_upscaling,
                    ssh_keypair=runner_args.ssh_keypair,
                    timeout=runner_args.cloud_timeout)
    else:
        if queue_name == 'local':
            queue = LocalQueue()
            queue.clean()
        elif queue_name.startswith('sqs_'):
            queue = SQSQueue(queue_name, verbose=verbose)
        else:
            queue = PubsubQueue(
                queue_name,
                config['database']['projectId'],
                verbose=verbose)

    for e in experiments:
        queue.enqueue(json.dumps({
            'experiment': e.__dict__,
            'config': config}))

    if queue_name == 'local':
        worker_args = ['studio-local-worker']

        if runner_args.config:
            worker_args += ['--config=' + runner_args.config]
        if runner_args.guest:
            worker_args += ['--guest']

        logger.info('worker args: {}'.format(worker_args))
        if not runner_args.num_workers or int(runner_args.num_workers) == 1:
            if 'STUDIOML_DUMMY_MODE' not in os.environ:
                local_worker.main(worker_args)
        else:
            raise NotImplementedError("Multiple local workers are not " +
                                      "implemented yet")
    return queue_name


def get_experiment_fitnesses(experiments, optimizer, config, logger):
    with model.get_db_provider() as db:
        progbar = Progbar(len(experiments), interval=0.0)
        logger.info("Waiting for fitnesses from %s experiments" %
                    len(experiments))

        bad_line_dicts = [dict() for x in xrange(len(experiments))]
        has_result = [False] * len(experiments)
        fitnesses = [0.0] * len(experiments)
        term_criterion = config['optimizer']['termination_criterion']
        skip_gen_thres = term_criterion['skip_gen_thres']
        skip_gen_timeout = term_criterion['skip_gen_timeout']
        result_timestamp = time.time()

        while sum(has_result) < len(experiments):
            for i, experiment in enumerate(experiments):
                if float(sum(has_result)) / len(experiments) >= skip_gen_thres\
                        and time.time() - result_timestamp > skip_gen_timeout:
                    logger.warn(
                        "Skipping to next gen with %s of solutions evaled" %
                        (float(
                            sum(has_result)) /
                            len(experiments)))
                    has_result = [True] * len(experiments)
                    break
                if has_result[i]:
                    continue
                returned_experiment = db.get_experiment(experiment.key,
                                                        getinfo=True)
                # try:
                #     experiment_output = returned_experiment.info['logtail']
                # except:
                #     logger.warn('Cannot access "logtail" in experiment.info')
                output = db._get_experiment_logtail(
                    returned_experiment)
                if output is None:
                    continue

                for j, line in enumerate(output):

                    if line.startswith(
                            "Traceback (most recent call last):") and \
                            j not in bad_line_dicts[i]:
                        logger.warn("Experiment %s: error"
                                    " discovered in output" %
                                    returned_experiment.key)
                        logger.warn("".join(output[j:]))
                        bad_line_dicts[i][j] = True

                    if line.startswith("Fitness") or \
                            line.startswith("fitness"):
                        try:
                            fitness = float(line.rstrip().split(':')[1])
                            # assert fitness >= 0.0
                        except BaseException:
                            if j not in bad_line_dicts[i]:
                                logger.warn(
                                    'Experiment %s: error parsing or invalid'
                                    ' fitness' %
                                    returned_experiment.key)
                                logger.warn(line)
                                bad_line_dicts[i][j] = True
                        else:
                            if fitness < 0.0:
                                logger.warn('Experiment %s: returned'
                                            ' fitness is less than zero,'
                                            ' setting it to zero' %
                                            returned_experiment.key)
                                fitness = 0.0

                            fitnesses[i] = fitness
                            has_result[i] = True
                            progbar.add(1)
                            result_timestamp = time.time()
                            break

            time.sleep(config['sleep_time'])
        print
        return fitnesses


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


def parse_hardware(runner_args, config={}):
    resources_needed = {}
    parse_list = ['gpus', 'cpus', 'ram', 'hdd']
    for key in parse_list:
        from_args = runner_args.__dict__.get(key)
        from_config = config.get(key)
        if from_args is not None:
            resources_needed[key] = from_args
        elif from_config is not None:
            resources_needed[key] = from_config

    return resources_needed


def add_hyperparam_experiments(
        exec_filename,
        other_args,
        runner_args,
        artifacts,
        resources_needed,
        logger,
        optimizer=None,
        hyperparam_tuples=None):

    experiment_name_base = runner_args.experiment if runner_args.experiment \
        else str(uuid.uuid4())

    project = runner_args.project if runner_args.project else \
        ('hyperparam_' + experiment_name_base)

    workspace_orig = artifacts['workspace']['local'] \
        if 'workspace' in artifacts.keys() else '.'

    ignore_arg = ''
    ignore_filepath = os.path.join(workspace_orig, ".studioml_ignore")
    if os.path.exists(ignore_filepath) and \
            not os.path.isdir(ignore_filepath):
        ignore_arg = "--exclude-from=%s" % ignore_filepath

    def create_experiments(hyperparam_tuples):
        experiments = []
        # experiment_names = {}
        for hyperparam_tuple in hyperparam_tuples:
            experiment_name = experiment_name_base
            experiment_name += "__opt__%s__%s" % (rand_string(32),
                                                  int(time.time()))
            experiment_name = experiment_name.replace('.', '_')

            workspace_new = fs_tracker.get_artifact_cache(
                'workspace', experiment_name)

            current_artifacts = artifacts.copy()
            current_artifacts.update({
                'workspace': {
                    'local': workspace_new,
                    'mutable': True
                }
            })

            rsync_cp(workspace_orig, workspace_new, ignore_arg, logger)
            # shutil.copytree(workspace_orig, workspace_new)

            for param_name, param_value in hyperparam_tuple.iteritems():
                if isinstance(param_value, np.ndarray):
                    array_filepath = '/tmp/%s.npy' % rand_string(32)
                    np.save(array_filepath, param_value)
                    assert param_name not in current_artifacts
                    current_artifacts[param_name] = {'local': array_filepath,
                                                     'mutable': False}
                else:
                    with open(os.path.join(workspace_new, exec_filename),
                              'rb') as f:
                        script_text = f.read()

                    script_text = re.sub(
                        '\\b' +
                        param_name +
                        '\\b(?=[^=]*\\n)',
                        str(param_value),
                        script_text)

                    with open(os.path.join(workspace_new, exec_filename),
                              'wb') as f:
                        f.write(script_text)

            experiments.append(model.create_experiment(
                filename=exec_filename,
                args=other_args,
                experiment_name=experiment_name,
                project=project,
                artifacts=current_artifacts,
                resources_needed=resources_needed,
                metric=runner_args.metric))
        return experiments

    if optimizer is not None:
        experiments = create_experiments(hyperparam_tuples)
    else:
        h = HyperparameterParser(runner_args, logger)
        hyperparam_tuples = h.convert_to_tuples(h.parse())
        experiments = create_experiments(hyperparam_tuples)

    return experiments


def add_packages(list1, list2):
    pkg_dict = {re.sub('==.+', '', pkg): pkg for pkg in list1 + list2}
    return [pkg for _, pkg in pkg_dict.iteritems()]


if __name__ == "__main__":
    main()
