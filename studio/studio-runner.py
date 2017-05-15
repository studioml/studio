#!/usr/bin/python

import sys
import subprocess


def run_job(filename, args):
    """Runs job while capturing environment and logging results.
    
    TODO: Implement executors, capturing state and results.
    """
    subprocess.run(["python", filename] + args)


def main():
    args = sys.argv
    if len(args) < 2:
        print("Usage: studio-runner myfile.py <args>")
        return
    exec_file, other_args = args[1], args[2:]
    run_job(exec_file, other_args)


if __name__ == "__main__":
    main()

