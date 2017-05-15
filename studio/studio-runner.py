#!/usr/bin/python

import sys
import subprocess


class LocalExecutor(object):
    """Runs job while capturing environment and logging results.

    TODO: capturing state and results.
    """

    def __init__(self):
        pass

    def run(self, filename, args):
        subprocess.run(["python", filename] + args)


def main():
    args = sys.argv
    if len(args) < 2:
        print("Usage: studio-runner myfile.py <args>")
        return
    exec_file, other_args = args[1], args[2:]
    # TODO: Queue the job based on arguments and only then execute.
    LocalExecutor().run(exec_filename, other_args)


if __name__ == "__main__":
    main()
