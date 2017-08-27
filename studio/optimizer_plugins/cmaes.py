import copy
import numpy as np
import cma
import math
import random
import copy

SIGMA0 = 0.25
EPSILON = 1e-12

# Overwrite the parameters of CMAES
OPTIMIZER_CONFIG = {
    'popsize': 3,
}

# Termination criterion for stopping CMAES
TERM_CRITERION = {
    'generation': 20, # Number of generation to run to
    'fitness': 999, # Threshold fitness to reach
    'skip_gen_thres': 1.0, # Fraction of results to get back before moving on
    'skip_gen_timeout': 999 # Timeout when skip_gen_thres activates
}

class Optimizer(object):
    def __init__(self, hyperparameters):
        self.hyperparameters = hyperparameters

        self.opts = cma.CMAOptions()
        for param, value in OPTIMIZER_CONFIG.iteritems():
            if param in self.opts and value is not None:
                self.opts[param] = value
        self.dim = 0
        for h in self.hyperparameters:
            assert self.dim == h.index
            self.dim += h.array_length if h.array_length is not None else 1

        self.init = np.empty(self.dim)
        self.sigma = SIGMA0
        self.gen = 0; self.best_fitness = 0.0; self.mean_fitness = 0.0

        for h in self.hyperparameters:
            if h.array_length is None:
                if h.rand_init:
                    self.init[h.index] = random.random() * (h.max_range - \
                        h.min_range) + h.min_range
                else:
                    self.init[h.index] = (h.max_range + h.min_range) / 2.0
            else:
                if h.rand_init:
                    self.init[h.index: h.index + h.array_length] = \
                        np.random.random(h.array_length) * (h.max_range - \
                        h.min_range) + h.min_range
                else:
                    self.init[h.index: h.index + h.array_length] = \
                        np.ones(h.array_length) * (h.max_range + h.min_range) \
                        / 2.0

        # print self.init
        self.es = cma.CMAEvolutionStrategy(self.init, self.sigma, self.opts)
        self.best_fitness = None
        self.best_solution = None


    def get_configs(self):
        return {'termination_criterion': TERM_CRITERION,
        'optimizer_config': OPTIMIZER_CONFIG}

    def __scale_var(self, var, min_range, max_range):
        return (var - min_range) / max((max_range - min_range), EPSILON)

    def __unscale_var(self, var, min_range, max_range):
        return (var * (max_range - min_range)) + min_range

    def __unpack_solution(self, solution):
        new_hyperparameters = []
        for h in self.hyperparameters:
            h = copy.copy(h)
            if h.array_length is None:
                h.values = solution[h.index]
            else:
                h.values = solution[h.index: h.index + h.array_length]
            if not h.unbounded:
                h.values = np.clip(h.values, h.min_range, h.max_range)
            h.values = self.__unscale_var(h.values, h.min_range, h.max_range)
            if h.is_log:
                h.values = np.exp(h.values)
            if h.array_length is None:
                h.values = float(h.values)
            new_hyperparameters.append(h)
        return new_hyperparameters

    def __pack_solution(self, hyperparameters):
        solution = np.empty(self.dim)
        for h in hyperparameters:
            values = copy.copy(h.values)
            if h.is_log:
                values = np.log(values)
            values = self.__scale_var(values, h.min_range, h.max_range)
            if not h.unbounded:
                values = np.clip(values, h.min_range, h.max_range)
            if h.array_length is None:
                solution[h.index] = values
            else:
                solution[h.index: h.index + h.array_length] = values

        return solution

    def stop(self):
        return self.gen >= TERM_CRITERION['generation'] or \
            self.best_fitness >= TERM_CRITERION['fitness']
        # return self.es.stop()

    def ask(self):
        solutions = self.es.ask()
        return [self.__unpack_solution(s) for s in solutions]

    def tell(self, hyperparameter_pop, fitnesses):
        adjusted_fitnesses = -1 * np.array(fitnesses)
        self.best_fitness = float(np.max(adjusted_fitnesses))
        self.mean_fitness = float(np.mean(adjusted_fitnesses))
        self.best_solution = np.argmax(adjusted_fitnesses)

        solutions = [self.__pack_solution(hyperparameters) for hyperparameters \
            in hyperparameter_pop]
        self.es.tell(solutions, adjusted_fitnesses)
        self.gen += 1

    def disp(self):
        print "best_fitness: %s mean fitness: %s" % (self.best_fitness,
            self.mean_fitness)
        self.es.disp()
