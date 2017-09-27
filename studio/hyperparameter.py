import itertools
import math

import numpy as np


class Hyperparameter(object):
    def __init__(
            self,
            name,
            index=None,
            values=None,
            min_range=None,
            max_range=None,
            array_length=None,
            unbounded=None,
            is_log=None,
            rand_init=None):

        self.name = name
        self.index = index
        self.values = values
        self.min_range = min_range
        self.max_range = max_range
        self.unbounded = unbounded
        self.is_log = is_log
        self.rand_init = rand_init
        self.array_length = array_length

    def is_compatible(self, h):
        return self.index == h.index and \
            self.array_length == h.array_length

    def __str__(self):
        my_str = "Hyperparameter: %s " % self.name
        if self.index is not None:
            my_str += "Index: %s " % self.index
        if self.values is not None:
            my_str += "Value: %s " % self.values
        if self.min_range is not None:
            my_str += "Min range: %s " % self.min_range
        if self.max_range is not None:
            my_str += "Max range: %s " % self.max_range
        if self.array_length is not None:
            my_str += "Array length: %s " % self.array_length
        if self.unbounded is not None:
            my_str += "Unbounded: %s " % self.unbounded
        if self.is_log is not None:
            my_str += "Log scale: %s " % self.is_log
        if self.rand_init is not None:
            my_str += "Rand init: %s " % self.rand_init
        return my_str


class HyperparameterParser(object):
    '''Class for parsing hyperparameters'''

    def __init__(self, runner_args, logger):
        self.runner_args = runner_args
        self.logger = logger

    def convert_to_tuples(self, hyperparameters):
        if self.runner_args.optimizer == "grid":
            all_hyperparam_values = []
            for h in hyperparameters:
                assert h.values is not None
                hyperparam_values = [(h.name, value) for value in h.values]
                all_hyperparam_values.append(hyperparam_values)

            hyperparam_tuples = []
            for item in itertools.product(*all_hyperparam_values):
                hyperparam_tuple = {}
                for name, param in item:
                    hyperparam_tuple[name] = param
                hyperparam_tuples.append(hyperparam_tuple)
        else:
            hyperparam_tuples = []
            for hyperparam_list in hyperparameters:
                hyperparam_dict = {}
                for h in hyperparam_list:
                    hyperparam_dict[h.name] = h.values
                hyperparam_tuples.append(hyperparam_dict)

        # print hyperparam_tuples
        return hyperparam_tuples

    def parse(self):
        self.index = 0
        hyperparameters = []
        for hyperparam in self.runner_args.hyperparam:
            param_name = hyperparam.split('=')[0]
            param_values_str = hyperparam.split('=')[1]
            if self.runner_args.optimizer == "grid":
                hyperparameters.append(self._parse_grid(param_name,
                                                        param_values_str))
            else:
                hyperparameters.append(self._parse_opt(param_name,
                                                       param_values_str))
        if self.runner_args.verbose:
            self.logger.info("Parsed the following hyperparameters:")
            for h in hyperparameters:
                self.logger.info(str(h))
        return hyperparameters

    def _parse_opt(self, param_name, range_str):
        unbounded = is_log = rand_init = False
        min_range = max_range = array_length = None
        raw_fields = range_str.split(":")

        correct_format = True
        flags = ""
        if len(raw_fields) > 2:
            flags = raw_fields[-1]
            allowed_flags = 'ualr'
            for letter in flags:
                if letter not in allowed_flags or flags.count(letter) != 1:
                    correct_format = False
            proper_field_length = 4 if "a" in flags else 3
            if len(raw_fields) != proper_field_length:
                correct_format = False
        elif len(raw_fields) < 2:
            correct_format = False

        if not correct_format:
            raise ValueError("Hyperparameter flags (%s) are incorrect for %s" %
                             (range_str, self.runner_args.optimizer))

        try:
            min_range = float(raw_fields[0])
            max_range = float(raw_fields[1])
            array_length = int(raw_fields[2]) if "a" in flags else None
            if array_length is not None and array_length <= 0:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Hyperparameter values (%s) are incorrect for %s" %
                (range_str, self.runner_args.optimizer))

        if min_range > max_range:
            raise ValueError("Min range (%s) is larger than max range (%s) " %
                             (min_range, max_range))

        unbounded = True if "u" in flags else False
        rand_init = True if "r" in flags else False
        if "l" in flags:
            is_log = True
            min_range = math.log(min_range)
            max_range = math.log(max_range)
        else:
            is_log = False

        if not hasattr(self, 'index'):
            self.index = 0
        h = Hyperparameter(
            param_name,
            index=self.index,
            min_range=min_range,
            max_range=max_range,
            array_length=array_length,
            unbounded=unbounded,
            is_log=is_log,
            rand_init=rand_init)
        self.index += array_length if array_length is not None else 1
        return h

    def _parse_grid(self, param_name, range_str):
        return_val = None
        if ',' in range_str:
            # return numpy array for consistency with other cases
            return_val = np.array([float(s) for s in range_str.split(',')])
        elif ':' in range_str:
            range_limits = range_str.split(':')
            assert len(range_limits) > 1
            if len(range_limits) == 2:
                try:
                    limit1 = float(range_limits[0])
                except ValueError:
                    limit1 = 0.0
                limit2 = float(range_limits[1])
                return_val = np.arange(limit1, limit2 + 1)
            else:
                try:
                    limit1 = float(range_limits[0])
                except ValueError:
                    limit1 = 0.0

                limit3 = float(range_limits[2])

                try:
                    limit2 = float(range_limits[1])
                    if int(limit2) == limit2 and limit2 > abs(limit3 - limit1):
                        return_val = np.linspace(limit1, limit3, int(limit2))
                    else:
                        return_val = np.arange(
                            limit1, limit3 + 0.5 * limit2, limit2)

                except ValueError:
                    if 'l' in range_limits[1]:
                        limit2 = int(range_limits[1].replace('l', ''))
                        return_val = np.exp(
                            np.linspace(
                                np.log(limit1),
                                np.log(limit3),
                                limit2))
                    else:
                        raise ValueError(
                            'unknown limit specification ' +
                            range_limits[1])

        else:
            return_val = [float(range_str)]
        if not isinstance(return_val, list):
            return_val = return_val.tolist()

        if not hasattr(self, 'index'):
            self.index = 0
        h = Hyperparameter(param_name, index=self.index, values=return_val)
        self.index += 1
        return h
