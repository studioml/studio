from local_worker import worker_loop
import sys
import logging
import time


from pubsub_queue import PubsubQueue

import argparse
logging.basicConfig()


def main(args=sys.argv):
    logger = logging.getLogger('studio-rworker')
    logger.setLevel(10)
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio remote worker. \
                     Usage: studio-rworker \
                     ')
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument(
        '--guest',
        help='Guest mode (does not require db credentials)',
        action='store_true')
    parser.add_argument('--queue', help='queue name', required=True)

    parsed_args, script_args = parser.parse_known_args(args)

    queue = PubsubQueue(parsed_args.queue)
    logger.info('Waiting for the work in the queue...')
    while not queue.has_next():
        time.sleep(5)
    logger.info('Starting working')
    worker_loop(queue, parsed_args,
                setup_pyenv=True,
                single_experiment=True,
                fetch_artifacts=True)


if __name__ == "__main__":
    main()
