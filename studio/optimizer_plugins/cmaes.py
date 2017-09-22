import cma
import random
import copy
import pickle
# import cPickle as pickle
import os
import pprint
import time
import six

import numpy as np

from opt_util import EPSILON


class Optimizer(object):

    def __init__(self, hyperparameters, config, logger):
        self.hyperparameters = hyperparameters
        self.config = config
        self.logger = logger

        self.opts = cma.CMAOptions()
        for param, value in six.iteritems(self.config['cmaes_config']):
            if param in self.opts and value is not None:
                self.opts[param] = value
        self.dim = 0
        for h in self.hyperparameters:
            assert self.dim == h.index
            self.dim += h.array_length if h.array_length is not None else 1

        self.init = np.empty(self.dim)
        # self.sigma = np.random.random(self.dim) # not allowed
        self.sigma = self.config['cmaes_config']['sigma0']
        self.opts['CMA_stds'] = np.ones(self.dim)
        self.gen = 0
        self.start_time = time.time()
        self.best_fitnesses = []
        self.mean_fitnesses = []
        self.best = None

        for h in self.hyperparameters:

            if h.array_length is None:
                if h.rand_init:
                    self.init[h.index] = random.random(
                    ) * (h.max_range - h.min_range) + h.min_range
                else:
                    self.init[h.index] = (h.max_range + h.min_range) / 2.0
            else:
                if h.rand_init:
                    self.init[h.index: h.index + h.array_length] = \
                        np.random.random(h.array_length) * \
                        (h.max_range - h.min_range) + h.min_range
                else:
                    self.init[h.index: h.index + h.array_length] = \
                        np.ones(h.array_length) * (h.max_range + h.min_range) \
                        / 2.0

            if h.array_length is None:
                if h.max_range - h.min_range > EPSILON:
                    self.opts['CMA_stds'][h.index] *= h.max_range - h.min_range
            else:
                if h.max_range - h.min_range > EPSILON:
                    self.opts['CMA_stds'][
                        h.index: h.index + h.array_length] *= \
                        h.max_range - h.min_range

        # If min range and max range are exactly the same,
        # use a sigma calculated
        # from mean of init
        # if max([h.max_range for h in hyperparameters]) - \
        #     min([h.min_range for h in hyperparameters]) < EPSILON:
        #     self.logger.warn("min range == max range, overwriting sigma0")
        #     self.sigma = np.mean(self.init) * MISC_CONFIG['sigma0']
        self.es = cma.CMAEvolutionStrategy(self.init, self.sigma, self.opts)
        self.__load_checkpoint()

        self.logger.info("Init: %s" % self.init)
        self.logger.info("CMA stds: %s" % self.opts['CMA_stds'])
        self.logger.info(pprint.pformat(self.get_config()))

    best_fitness = property(lambda self: self.best_fitnesses[-1]
                            if len(self.best_fitnesses) > 0 else 0.0)

    mean_fitness = property(lambda self: self.mean_fitnesses[-1]
                            if len(self.mean_fitnesses) > 0 else 0.0)

    def get_config(self):
        return self.config['cmaes_config']

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
            # if h.max_range - h.min_range < EPSILON:
            #     h.values = unscale_var(h.values, h.min_range, h.max_range)
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
            # if h.max_range - h.min_range < EPSILON:
            #     values = scale_var(values, h.min_range, h.max_range)
            if not h.unbounded:
                values = np.clip(values, h.min_range, h.max_range)
            if h.array_length is None:
                solution[h.index] = values
            else:
                solution[h.index: h.index + h.array_length] = values
        # print solution
        return solution

    def stop(self):
        term_criterion = self.config['termination_criterion']

        if self.gen >= term_criterion['generation']:
            self.logger.info("Reached target generation %s, terminating" %
                             term_criterion['generation'])
            return True
        elif self.best_fitness >= term_criterion['fitness']:
            self.logger.info("Reached target fitness %s, terminating" %
                             term_criterion['fitness'])
            return True
        return False
        # return self.es.stop()

    def ask(self):
        solutions = self.es.ask()
        return [self.__unpack_solution(s) for s in solutions]

    def tell(self, hyperparameter_pop, fitnesses):
        adjusted_fitnesses = -1 * np.array(fitnesses)
        self.best_fitnesses.append(float(np.max(fitnesses)))
        self.mean_fitnesses.append(float(np.mean(fitnesses)))
        self.best = (hyperparameter_pop[np.argmax(fitnesses)],
                     self.__pack_solution(
            hyperparameter_pop[np.argmax(fitnesses)]))

        solutions = [self.__pack_solution(hyperparameters) for hyperparameters
                     in hyperparameter_pop]
        self.es.tell(solutions, adjusted_fitnesses)
        self.gen += 1
        self.__save_checkpoint()

    def disp(self):
        print("**************************************************************")
        print("CMAES wall time: %s gen: %s pop size: %s best fitness: "
              "%s mean fitness: %s" % (int(time.time() - self.start_time),
                                       self.gen, self.es.popsize,
                                       self.best_fitness, self.mean_fitness))
        print("**************************************************************")

    def __load_checkpoint(self):
        if self.config['load_checkpoint_file'] is None:
            return
        try:
            checkpoint_file = os.path.abspath(os.path.expanduser(
                self.config['load_checkpoint_file']))
            with open(checkpoint_file) as f:
                old_cmaes_instance = pickle.load(f)
        except BaseException:
            self.logger.warn("Checkpoint file cannot be loaded")
            raise

        for h, h_old in zip(self.hyperparameters,
                            old_cmaes_instance.hyperparameters):
            assert h.is_compatible(h_old)

        if self.config['cmaes_config']['load_best_only']:
            self.init = old_cmaes_instance.best[1]
            self.es = cma.CMAEvolutionStrategy(self.init, self.sigma,
                                               self.opts)
            self.logger.info("Loaded best solution as init")
        else:
            logger = self.logger
            config = self.config
            self.__dict__ = old_cmaes_instance.__dict__
            self.logger = logger
            self.config = config

        self.logger.info("Loaded checkpoint from file: %s" % checkpoint_file)

    def __save_checkpoint(self):
        if (int(self.config['checkpoint_interval']) >= 1 and
            self.gen % int(self.config['checkpoint_interval']) == 0) or \
                self.stop():

            try:
                result_dir = os.path.abspath(
                    os.path.expanduser(self.config['result_dir']))
                if not os.path.exists(result_dir):
                    os.makedirs(result_dir)
            except BaseException:
                self.looger.warn("Cannot retrieve checkpoint directory,"
                                 " not saving checkpoint")
                return

            checkpoint_file = os.path.join(
                result_dir, "G%s_F%s_checkpoint.pkl" %
                (self.gen, self.best_fitness))
            with open(checkpoint_file, 'wb') as f:
                copy_of_self = copy.copy(self)
                copy_of_self.logger = None
                copy_of_self.config = None
                # copy_of_self.es = None
                pickle.dump(copy_of_self, f, protocol=-1)

            best_file = os.path.join(
                result_dir, "G%s_F%s_best.pkl" %
                (self.gen, self.best_fitness))
            with open(best_file, 'wb') as f:
                pickle.dump(self.best, f, protocol=-1)

            with open(os.path.join(result_dir, "fitness.txt"), 'wb') as f:
                for best, mean in zip(
                        self.best_fitnesses, self.mean_fitnesses):
                    f.write("%s %s\n" % (best, mean))

            self.logger.info("Saved checkpoint to file: %s" % checkpoint_file)
