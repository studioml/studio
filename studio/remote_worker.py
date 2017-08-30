from local_worker import worker_loop
import sys
import logging
import time
import model


from pubsub_queue import PubsubQueue
from sqs_queue import SQSQueue

import argparse
logging.basicConfig()


def main(args=sys.argv):
    logger = logging.getLogger('studio-remote-worker')
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio remote worker. \
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
        default=None)

    parsed_args, script_args = parser.parse_known_args(args)
    verbose = model.parse_verbosity(parsed_args.verbose)
    logger.setLevel(verbose)
    if parsed_args.queue.startswith('ec2_') or \
       parsed_args.queue.startswith('sqs_'):
        queue = SQSQueue(parsed_args.queue, verbose=verbose)
    else:
        queue = PubsubQueue(parsed_args.queue, verbose=verbose)
    logger.info('Waiting for the work in the queue...')

    wait_time = 0
    wait_step = 5
    while not queue.has_next():
        logger.info(
            'No messages found, sleeping for {} s (total wait time {} s)'
            .format(wait_step, wait_time))
        time.sleep(wait_step)
        wait_time += wait_step
        if parsed_args.timeout and int(parsed_args.timeout) < wait_time:
            logger.info('No jobs found in the queue during {} s'.
                        format(parsed_args.timeout))
            return

    logger.info('Starting working')
    worker_loop(queue, parsed_args,
                setup_pyenv=True,
                single_experiment=parsed_args.single_run,
                fetch_artifacts=True)


if __name__ == "__main__":
    main()
