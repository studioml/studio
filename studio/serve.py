import shutil
import os
import sys
import time
import uuid
import argparse
from . import runner, fs_tracker

# `studio serve <key> --preprocessing blabla.py ` under the hood will run something like
# studio run --reuse <key>/modeldir:modeldata serve_main.py  --preprocessing blabla.py


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--preprocessing','-p', default=None)
    
    options, other_args = argparser.parse_known_args(sys.argv[1:])
    serve_args = ['studio::serve_main']

    assert len(other_args) >= 1
    experiment_key = other_args[-1]
    runner_args = other_args[:-1]
    runner_args.append('--reuse={}/modeldir:modeldata'.format(experiment_key))
    runner_args.append('--force-git')

    if options.preprocessing:
        serve_args.append('--preprocessing=' + options.preprocessing)
        
    total_args = runner_args + serve_args
    runner.main(total_args)

if __name__ == '__main__':
    main()

