import hashlib
from io import StringIO
from datetime import timedelta
import re
import random
import string
import struct
import time
import sys
import shutil
import subprocess
import os
import numpy as np
import requests
import tempfile
import uuid
from studio.storage import storage_setup
from studio.storage.storage_type import StorageType

def event_reader(fileobj):
    from tensorflow.core.util import event_pb2

    if isinstance(fileobj, str):
        fileobj = open(fileobj, 'rb')

    header_len = 12
    footer_len = 4
    size_len = 8

    while True:
        try:
            data_len = struct.unpack('Q', fileobj.read(size_len))[0]
            fileobj.read(header_len - size_len)

            data = fileobj.read(data_len)

            event = None
            event = event_pb2.Event()
            event.ParseFromString(data)

            fileobj.read(footer_len)
            yield event
        except BaseException:
            check_for_kb_interrupt()
            break

    fileobj.close()

def get_experiment_metric(experiment):
    info = dict()
    info['metric_value'] = None
    if experiment.metric is not None:
        metric_str = experiment.metric.split(':')
        metric_name = metric_str[0]
        metric_type = metric_str[1] if len(metric_str) > 1 else None

        tb_art = experiment.artifacts['tb']
        tbtar = tb_art.stream() if tb_art else None

        if metric_type == 'min':
            def metric_accum(x, y):
                return min(x, y) if x else y
        elif metric_type == 'max':
            def metric_accum(x, y):
                return max(x, y) if x else y
        else:
            def metric_accum(x, y):
                return y

        metric_value = None
        if tbtar is not None:
            for f in tbtar:
                if f.isreg():
                    for e in util.event_reader(tbtar.extractfile(f)):
                        for v in e.summary.value:
                            if v.tag == metric_name:
                                metric_value = metric_accum(
                                    metric_value, v.simple_value)

        info['metric_value'] = metric_value
    return info

def rsync_cp(source, dest, ignore_arg='', logger=None):
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest) if os.path.isdir(dest) else os.remove(dest)
        os.makedirs(dest)
    except OSError:
        pass

    if ignore_arg != '':
        source += "/"
        tool = 'rsync'
        args = [tool, ignore_arg, '-aHAXE', source, dest]
    else:
        try:
            os.rmdir(dest)
        except OSError:
            pass

        tool = 'cp'
        args = [
            tool,
            '-pR',
            source,
            dest
        ]

    pcp = subprocess.Popen(args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
    cpout, _ = pcp.communicate()
    if pcp.returncode != 0 and logger is not None:
        logger.info('%s returned non-zero exit code. Output:' % tool)
        logger.info(cpout)


class Progbar(object):
    """Displays a progress bar.

    # Arguments
        target: Total number of steps expected, None if unknown.
        interval: Minimum visual progress update interval (in seconds).
    """

    def __init__(self, target, width=30, verbose=1, interval=0.05):
        self.width = width
        if target is None:
            target = -1
        self.target = target
        self.sum_values = {}
        self.unique_values = []
        self.start = time.time()
        self.last_update = 0
        self.interval = interval
        self.total_width = 0
        self.seen_so_far = 0
        self.verbose = verbose

    def update(self, current, values=None, force=False):
        """Updates the progress bar.

        # Arguments
            current: Index of current step.
            values: List of tuples (name, value_for_last_step).
                The progress bar will display averages for these values.
            force: Whether to force visual progress update.
        """
        values = values or []
        for k, v in values:
            if k not in self.sum_values:
                self.sum_values[k] = [v * (current - self.seen_so_far),
                                      current - self.seen_so_far]
                self.unique_values.append(k)
            else:
                self.sum_values[k][0] += v * (current - self.seen_so_far)
                self.sum_values[k][1] += (current - self.seen_so_far)
        self.seen_so_far = current

        now = time.time()
        if self.verbose == 1:
            if not force and (now - self.last_update) < self.interval:
                return

            prev_total_width = self.total_width
            sys.stdout.write('\b' * prev_total_width)
            sys.stdout.write('\r')

            if self.target != -1:
                numdigits = int(np.floor(np.log10(self.target))) + 1
                barstr = '%%%dd/%%%dd [' % (numdigits, numdigits)
                bar = barstr % (current, self.target)
                prog = float(current) / self.target
                prog_width = int(self.width * prog)
                if prog_width > 0:
                    bar += ('=' * (prog_width - 1))
                    if current < self.target:
                        bar += '>'
                    else:
                        bar += '='
                bar += ('.' * (self.width - prog_width))
                bar += ']'
                sys.stdout.write(bar)
                self.total_width = len(bar)

            if current:
                time_per_unit = (now - self.start) / current
            else:
                time_per_unit = 0
            eta = time_per_unit * (self.target - current)
            info = ''
            if current < self.target and self.target != -1:
                info += ' - ETA: %ds' % eta
            else:
                info += ' - %ds' % (now - self.start)
            for k in self.unique_values:
                info += ' - %s:' % k
                if isinstance(self.sum_values[k], list):
                    avg = np.mean(
                        self.sum_values[k][0] / max(1, self.sum_values[k][1]))
                    if abs(avg) > 1e-3:
                        info += ' %.4f' % avg
                    else:
                        info += ' %.4e' % avg
                else:
                    info += ' %s' % self.sum_values[k]

            self.total_width += len(info)
            if prev_total_width > self.total_width:
                info += ((prev_total_width - self.total_width) * ' ')

            sys.stdout.write(info)
            sys.stdout.flush()

            if current >= self.target:
                sys.stdout.write('\n')

        if self.verbose == 2:
            if current >= self.target:
                info = '%ds' % (now - self.start)
                for k in self.unique_values:
                    info += ' - %s:' % k
                    avg = np.mean(
                        self.sum_values[k][0] / max(1, self.sum_values[k][1]))
                    if avg > 1e-3:
                        info += ' %.4f' % avg
                    else:
                        info += ' %.4e' % avg
                sys.stdout.write(info + "\n")

        self.last_update = now

    def add(self, n, values=None):
        self.update(self.seen_so_far + n, values)


def has_aws_credentials():
    artifact_store = storage_setup.get_storage_artifact_store()
    if artifact_store is None:
        return False
    storage_handler = artifact_store.get_storage_handler()
    if storage_handler.type == StorageType.storageS3:
        storage_client = storage_handler.get_client()
        return storage_client._request_signer._credentials is not None
    else:
        return False

