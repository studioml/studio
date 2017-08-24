import copy
import numpy as np
import cma
import math

SIGMA0 = 0.25
EPSILON = 1e-9

# Overwrite the parameters of CMAES
OPTIMIZER_CONFIG = {
    'popsize': 2,
}

# Termination criterion for stopping CMAES
TERM_CRITERION = {
    'generation': 2, # Number of generation to run to
    'fitness': 999, # Threshold fitness to reach
    'skip_gen_thres': 0.95, # Fraction of results to get back before moving on
}

class Optimizer(object):
    def __init__(self, hyperparam_dict, log_scale_dict):
        self.hyperparam_dict = hyperparam_dict
        self.log_scale_dict = log_scale_dict
        self.nametoi = {}; self.itoname = {}
        self.init = []
        self.sigma = SIGMA0
        self.bounds = []
        self.gen = 0
        self.best_fitness = 0.0

        for i, name in enumerate(hyperparam_dict):
            self.itoname[i] = name
            self.nametoi[name] = i
            if log_scale_dict[name]:
                values = np.log(hyperparam_dict[name])
            else:
                values = hyperparam_dict[name]
            self.bounds.append((np.min(values), np.max(values)))
            self.init.append(self.scale_var(np.median(values), np.min(values),
                np.max(values)))

        self.opts = cma.CMAOptions()
        self.opts.update(OPTIMIZER_CONFIG)
        self.es = cma.CMAEvolutionStrategy(np.array(self.init), self.sigma,
            self.opts)

    def get_config(self):
        return OPTIMIZER_CONFIG

    def get_term_criterion(self):
        return TERM_CRITERION

    def scale_var(self, var, min_value, max_value):
        return (var - min_value) / max((max_value - min_value), EPSILON)

    def __unpack_solution(self, solution):
        solution_dict = {}
        for i in xrange(len(solution)):
            name = self.itoname[i]
            if self.log_scale_dict[name]:
                solution_dict[name] = math.exp(solution[i])
            else:
                solution_dict[name] = float(solution[i])
            min_value, max_value = self.bounds[i]

            solution_dict[name] = min(max_value, max(min_value,
                solution_dict[name]))
        return solution_dict

    def __pack_solution(self, hyperparam_dict):
        solution = np.empty(len(hyperparam_dict))
        for name in hyperparam_dict:
            index = self.nametoi[name]
            if self.log_scale_dict[name]:
                solution[index] = math.log(hyperparam_dict[name])
            else:
                solution[index] = hyperparam_dict[name]
        return solution

    def stop(self):
        return self.gen >= TERM_CRITERION['generation'] or \
            self.best_fitness >= TERM_CRITERION['fitness']
        # return self.es.stop()

    def ask(self):
        solutions = self.es.ask()
        return [self.__unpack_solution(s) for s in solutions]

    def tell(self, hyperparam_dicts, fitnesses):
        adjusted_fitnesses = -1 * np.array(fitnesses)
        self.best_fitness = -1 * float(np.max(adjusted_fitnesses))
        solutions = [self.__pack_solution(h) for h in hyperparam_dicts]
        self.es.tell(solutions, adjusted_fitnesses)
        self.gen += 1

    def disp(self):
        self.es.disp()
