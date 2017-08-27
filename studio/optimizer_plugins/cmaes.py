import cma
import random
import copy
import cPickle as pickle
import os
import pprint

import numpy as np

# Overwrite the parameters of CMAES implementation
OPT_CONFIG = {
    'popsize': 2,
}

# Misc configuration for this wrapper class only
MISC_CONFIG = {
    'epsilon': 1e-12,
    'sigma0': 0.33
}

# Termination criterion for stopping CMAES
# TERM_CRITERION = {
#     'generation': 20, # Number of generation to run to
#     'fitness': 999, # Threshold fitness to reach
#     'skip_gen_thres': 1.0, # Fraction of results to get back before moving on
#     'skip_gen_timeout': 999 # Timeout when skip_gen_thres activates
# }

class Optimizer(object):
    def __init__(self, hyperparameters, config, logger):
        self.hyperparameters = hyperparameters
        self.config = config
        self.logger = logger

        self.opts = cma.CMAOptions()
        for param, value in OPT_CONFIG.iteritems():
            if param in self.opts and value is not None:
                self.opts[param] = value
        self.dim = 0
        for h in self.hyperparameters:
            assert self.dim == h.index
            self.dim += h.array_length if h.array_length is not None else 1

        self.init = np.empty(self.dim)
        # self.sigma = np.random.random(self.dim) # not allowed
        self.sigma = MISC_CONFIG['sigma0']
        self.opts['CMA_stds'] = np.ones(self.dim)
        self.gen = 0
        self.best_fitness = self.mean_fitness = 0.0
        self.best_hyperparam = None

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

            if h.array_length is None:
                if h.max_range - h.min_range > MISC_CONFIG['epsilon']:
                    self.opts['CMA_stds'][h.index] *= h.max_range - h.min_range
            else:
                if h.max_range - h.min_range > MISC_CONFIG['epsilon']:
                    self.opts['CMA_stds'][h.index: h.index + h.array_length] *= \
                        h.max_range - h.min_range

        # If min range and max range are exactly the same, use a sigma calculated
        # from mean of init
        # if max([h.max_range for h in hyperparameters]) - \
        #     min([h.min_range for h in hyperparameters]) < MISC_CONFIG['epsilon']:
        #     self.logger.warn("min range == max range, overwriting sigma0")
        #     self.sigma = np.mean(self.init) * MISC_CONFIG['sigma0']
        self.logger.info("Init: %s" % self.init)
        self.logger.info("CMA stds: %s" % self.opts['CMA_stds'])
        self.es = cma.CMAEvolutionStrategy(self.init, self.sigma, self.opts)

        self.logger.info(pprint.pformat(self.get_configs()))

    def get_configs(self):
        return {'optimizer_config': self.opts, 'misc_config': MISC_CONFIG}

    def __scale_var(self, var, min_range, max_range):
        return (var - min_range) / max((max_range - min_range),
            MISC_CONFIG['epsilon'])

    def __unscale_var(self, var, min_range, max_range):
        return (var * (max_range - min_range)) + min_range

    def __unpack_solution(self, solution):
        # print solution
        new_hyperparameters = []
        for h in self.hyperparameters:
            h = copy.copy(h)
            if h.array_length is None:
                h.values = solution[h.index]
            else:
                h.values = solution[h.index: h.index + h.array_length]
            if not h.unbounded:
                h.values = np.clip(h.values, h.min_range, h.max_range)
            # if h.max_range - h.min_range < MISC_CONFIG['epsilon']:
            #     h.values = self.__unscale_var(h.values, h.min_range, h.max_range)
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
            # if h.max_range - h.min_range < MISC_CONFIG['epsilon']:
            #     values = self.__scale_var(values, h.min_range, h.max_range)
            if not h.unbounded:
                values = np.clip(values, h.min_range, h.max_range)
            if h.array_length is None:
                solution[h.index] = values
            else:
                solution[h.index: h.index + h.array_length] = values
        # print solution
        return solution

    def stop(self):
        term_criterion = self.config['optimizer']['termination_criterion']

        if self.gen >= term_criterion['generation']:
            self.logger.info("Reached target generation %s, terminating" % \
                term_criterion['generation'])
            return True
        elif self.best_fitness >= term_criterion['fitness']:
            self.logger.info("Reached target fitness %s, terminating" % \
                term_criterion['fitness'])
            return True
        return False
        # return self.es.stop()

    def ask(self):
        solutions = self.es.ask()
        return [self.__unpack_solution(s) for s in solutions]

    def tell(self, hyperparameter_pop, fitnesses):
        adjusted_fitnesses = -1 * np.array(fitnesses)
        self.best_fitness = float(np.max(fitnesses))
        self.mean_fitness = float(np.mean(fitnesses))
        self.best_hyperparam = hyperparameter_pop[np.argmax(fitnesses)]

        solutions = [self.__pack_solution(hyperparameters) for hyperparameters \
            in hyperparameter_pop]
        self.es.tell(solutions, adjusted_fitnesses)
        self.gen += 1

    def disp(self):
        print "*****************************************************************"
        print "CMAES gen: %s pop size: %s best fitness: " \
            "%s mean fitness: %s" % (self.gen, self.es.popsize, \
            self.best_fitness, self.mean_fitness)
        print "*****************************************************************"
        # return self.gen, self.best_fitness, self.best_hyperparam
        # self.logger.info("CMAES gen: %s pop size: %s best fitness: "
        #     "%s mean fitness: %s" % (self.gen, self.es.popsize,
        #     self.best_fitness, self.mean_fitness))

    def save_checkpoint(self):
        if (self.config['optimizer']['checkpoint_interval'] >= 1 and self.gen % \
            self.config['optimizer']['checkpoint_interval'] == 0) or \
            self.stop():

            with open(os.path.join(os.path.abspath( \
                os.path.expanduser(self.config['optimizer']['result_dir'])), \
                "G%s_F%s_hyperparam.pkl" % (self.gen, self.best_fitness)), \
                'wb') as f:
                pickle.dump(self.best_hyperparam, f, protocol=-1)
