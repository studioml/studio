import sys
import argparse

from . import model, logs
from .local_worker import worker_loop
from .pubsub_queue import PubsubQueue
from .sqs_queue import SQSQueue
from .util import parse_verbosity

from .qclient_cache import get_cached_queue


def main(args=sys.argv):
    logger = logs.getLogger('studio-remote-worker')
    parser = argparse.ArgumentParser(
        description='Studio remote worker. \
                     Usage: studio-remote-worker \
                     ')
    parser.add_argument('--config', help='configuration file', default=None)

    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')

    parser.add_argument(
        '--single-run',
        help='quit after a single run (regardless of the state of the queue)',
        action='store_true')

    parser.add_argument('--queue', help='queue name', required=True)
    parser.add_argument(
        '--verbose', '-v',
        help='Verbosity level. Allowed vaules: ' +
             'debug, info, warn, error, crit ' +
             'or numerical value of logger levels.',
        default=None)

    parser.add_argument(
        '--timeout', '-t',
        help='Timeout after which remote worker stops listening (in seconds)',
        type=int,
        default=100)

    parsed_args, script_args = parser.parse_known_args(args)
    verbose = parse_verbosity(parsed_args.verbose)
    logger.setLevel(verbose)

    config = None
    if parsed_args.config is not None:
        config = model.get_config(parsed_args.config)

    if parsed_args.queue.startswith('ec2_') or \
       parsed_args.queue.startswith('sqs_'):
        queue = SQSQueue(parsed_args.queue, verbose=verbose)
    elif parsed_args.queue.startswith('rmq_'):
        queue = get_cached_queue(
            name=parsed_args.queue,
            route='StudioML.' + parsed_args.queue,
            config=config,
            logger=logger,
            verbose=verbose)
    else:
        queue = PubsubQueue(parsed_args.queue, verbose=verbose)

    logger.info('Waiting for work')

    timeout_before = parsed_args.timeout
    timeout_after = timeout_before if timeout_before > 0 else 0
    # wait_for_messages(queue, timeout_before, logger)

    logger.info('Starting working')
    worker_loop(queue, parsed_args,
                single_experiment=parsed_args.single_run,
                timeout=timeout_after,
                verbose=verbose)


if __name__ == "__main__":
    main()
