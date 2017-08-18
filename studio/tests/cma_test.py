#!/usr/bin/python
import os, sys, time, random, pprint

import cma
import numpy as np

def objective_func(x):
  return np.sum(x*x)

def main():
  opts = cma.CMAOptions()
  opts['popsize'] = 15
  es = cma.CMAEvolutionStrategy(np.random.random(8), 0.1, opts)
  while not es.stop():
    solutions = es.ask()
    es.tell(solutions, [objective_func(s) for s in solutions])
    es.disp()
  es.result_pretty()
  pprint.pprint(opts)

if __name__== "__main__":
  main()