#!/usr/bin/env python

import os
import sys
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except BaseException:
    pass

EPSILON = 1e-12


def scale_var(var, min_range, max_range):
    return (var - min_range) / max((max_range - min_range), EPSILON)


def unscale_var(var, min_range, max_range):
    return (var * (max_range - min_range)) + min_range


def visualize_fitness(fitness_file=None, best_fitnesses=None,
                      mean_fitnesses=None, outfile="fitness.png"):
    if best_fitnesses is None or mean_fitnesses is None:
        assert os.path.exists(fitness_file)
        best_fitnesses = []
        mean_fitnesses = []
        with open(fitness_file) as f:
            for line in f.readlines():
                best_fit, mean_fit = [float(x) for x in line.rstrip().split()]
                best_fitnesses.append(best_fit)
                mean_fitnesses.append(mean_fit)

        plt.figure(figsize=(16, 12))
        plt.plot(np.arange(len(best_fitnesses)), best_fitnesses,
                 label="Best Fitness")
        plt.plot(np.arange(len(mean_fitnesses)), mean_fitnesses,
                 label="Mean Fitness")
        plt.xlabel("Generation")
        plt.ylabel("Fitness")
        plt.grid()
        plt.legend(loc='lower right')

        outfile = os.path.abspath(os.path.expanduser(outfile))
        plt.savefig(outfile, bbox_inches='tight')


if __name__ == "__main__":
    func = eval(sys.argv[1])
    func(*sys.argv[2:])
