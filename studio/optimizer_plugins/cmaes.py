import copy
import numpy as np
import cma
import math
import random

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
    'skip_gen_thres': 0.5, # Fraction of results to get back before moving on
    'skip_gen_timeout': 0.0 # Timeout when skip_gen_thres activates
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
        for h in self.hyperparmeters:
            if h.array_length is None:
                if h.rand_init:
                    self.init[h.index] = random.random() * (h.max_value - \
                        h.min_value) + h.min_value
                else:
                    self.init[h.index] = (h.max_value + h.min_value) / 2.0
            else:
                if h.rand_init:
                    self.init[h.index, h.index + h.array_length] = \
                        np.random.random(h.array_length) * (h.max_value - \
                        h.min_value) + h.min_value
                else:
                    self.init[h.index, h.index + h.array_length] = \
                        np.ones(h.array_length) * (h.max_value + h.min_value) \
                        / 2.0

        self.es = cma.CMAEvolutionStrategy(self.init, self.sigma, self.opts)
        self.best_fitness = None
        self.best_solution = None


    def get_configs(self):
        return {'termination_criterion': TERM_CRITERION,
        'optimizer_config': OPTIMIZER_CONFIG}

    def __scale_var(self, var, min_value, max_value):
        return (var - min_value) / max((max_value - min_value), EPSILON)

    def __unscale_var(self, var, min_value, max_value):
        return (var * (max_value - min_value)) + min_value

    def __unpack_solution(self, solution):
        for h in self.hyperparameters:
            if h.array_length is None:
                h.values = solution[h.index]
            else:
                h.values = solutution[h.index: h.index + h.array_length]
            if not h.unbounded:
                h.values = np.clip(h.values, h.min_value, h.max_value)
            h.values = self.__unscale_var(h.values, h.min_value, h.max_value)
            if h.is_log:
                h.values = np.exp(h.values)
            if h.array_length is None:
                h.values = float(h.values)

        return self.hyperparameters

    def __pack_solution(self, hyperparam_dict):
        solution = np.empty(self.dim)
        for h in self.hyperparameters:
            values = copy.copy(h.values)
            if h.is_log:
                values = np.log(values)
            values = self.__scale_var(values, h.min_value, h.max_value)
            if not h.unbounded:
                values = np.clip(values, h.min_value, h.max_value)
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

    def tell(self, hyperparameters, fitnesses):
        adjusted_fitnesses = -1 * np.array(fitnesses)
        self.best_fitness = float(np.max(adjusted_fitnesses))
        self.best_solution = np.argmx(adjusted_fitnesses)

        solutions = [self.__pack_solution(h) for h in hyperparameters]
        self.es.tell(solutions, adjusted_fitnesses)
        self.gen += 1

    def disp(self):
        self.es.disp()
