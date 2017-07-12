from local_worker import worker_loop
import sys
import logging
import time
import model


from pubsub_queue import PubsubQueue

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

    parsed_args, script_args = parser.parse_known_args(args)
    verbose = model.parse_verbosity(parsed_args.verbose)
    logger.setLevel(verbose)
    queue = PubsubQueue(parsed_args.queue, verbose=verbose)
    logger.info('Waiting for the work in the queue...')
    while not queue.has_next():
        time.sleep(5)
    logger.info('Starting working')
    worker_loop(queue, parsed_args,
                setup_pyenv=True,
                single_experiment=parsed_args.signle_run,
                fetch_artifacts=True)


if __name__ == "__main__":
    main()
