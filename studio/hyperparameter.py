import os
import sys
import traceback
import numpy as np

class Hyperparameter(object):
    def __init__(self, name, values=None, min_range=None, max_range=None,
        array_length=None, unbounded=False, is_log=False, rand_init=False):

        self.name = name
        self.values = values
        self.min_range = min_range
        self.max_range = max_range
        self.unbounded = unbounded
        self.is_log = is_log
        self.rand_init = rand_init
        self.length = array_length

class HyperparameterParser(object):
  '''Class for parsing hyperparameters'''

    def __init__(self, optimizer_type, hyperparam_list):
        self.optimizer_type = optimizer_type
        self.hyperparam_list = hyperparam_list
        self.hyperparameters = []

        for hyperparam in runner_args.hyperparam:
            param_name = hyperparam.split('=')[0]
            param_values_str = hyperparam.split('=')[1]
            if self.optimizer_type == "grid":
                self.hyperparameters.append(self.parse_grid(param_name,
                    param_values_str))
            else:
                self.hyperparameters.append(self.parse_opt(param_name,
                    param_values_str))

    def parse_opt(self, param_name, range_str):
        unbounded = is_log = rand_init = False
        min_value = max_value = array_length = None
        raw_fields = range_str.split(":")

        correct_format = True
        if length(raw_fields) > 2
            flags = raw_fields[0]

            allowed_flags = 'ualr'
            if len(flags) > len(allowed_flags):
                correct_format = False
            for letter in flags:
                if letter not in allowed_flags:
                    correct_format = False
            proper_field_length = 4 if "a" in flags else 3
            if len(raw_fields) != proper_field_length:
                correct_format = False

        elif length(raw_fields) < 2:
            correct_format = False
        else:
            flags = ""
        if not correct_format:
            raise ValueError("Hyperparameter format (%s) is incorrect for %s",
                        (range_str, self.optimizer_type))

        min_value = float(raw_fields[1])
        max_value = float(raw_fields[2])
        array_length = int(raw_fields[3]) if "a" in flags else None

        unbounded = True if "u" in flags else False
        is_log = True if "l" in flags else False
        rand_init = True if "r" in flags else False

        return Hyperparameter(param_name, min_value=min_value,
            max_value=max_value, array_length=array_length, unbounded=unbounded,
            is_log=is_log, rand_init=rand_init)

    def parse_grid(self, param_name, range_str):
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
                        return_val = np.arange(limit1, limit3 + 0.5 * limit2, limit2)

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
        return Hyperparameter(param_name, values=return_val)
