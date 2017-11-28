import shutil
import os
import sys
import time
import uuid
import argparse
from . import runner, fs_tracker


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--wrapper', '-w', default=None)
    argparser.add_argument('--port', default=5000)
    argparser.add_argument('--host', default='0.0.0.0')

    options, other_args = argparser.parse_known_args(sys.argv[1:])
    serve_args = ['studio::serve_main']

    assert len(other_args) >= 1
    experiment_key = other_args[-1]
    runner_args = other_args[:-1]
    runner_args.append('--reuse={}/modeldir:modeldata'.format(experiment_key))
    runner_args.append('--force-git')
    runner_args.append('--port=' + str(options.port))

    if options.preprocessing:
        serve_args.append('--wrapper=' + options.wrapper)
        serve_args.append('--port=' + str(options.port))

    serve_args.append('--host=' + options.host)

    total_args = runner_args + serve_args
    runner.main(total_args)


if __name__ == '__main__':
    main()
