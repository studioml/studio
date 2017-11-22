import shutil
import os
import sys
from . import runner

# `studio serve <key> --preprocessing blabla.py ` under the hood will run something like
# studio run --reuse <key>/modeldir:modeldata _serve.py  --preprocessing blabla.py


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--preprocessing','-p', default=None)
    
    options, runner_args = argparser.parse_known_args(sys.argv[1:])
    serve_args = ['serve_main.py']

    if options.preprocessing:
        serve_args.append('--preprocessing=' + options.preprocessing)

    
    


if __name__ == '__main__':
    main()

