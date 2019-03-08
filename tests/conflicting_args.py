import argparse
import sys


parser = argparse.ArgumentParser(description='Test argument conflict')
parser.add_argument('--experiment', '-e', help='experiment key', required=True)
args = parser.parse_args()

print("Experiment key = " + args.experiment)
sys.stdout.flush()
