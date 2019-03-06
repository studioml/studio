"""Tools to simplify PyTorch reporting and integrate with TensorBoard."""

import collections
import six
import time

try:
    from tensorflow import summary as tb_summary
except ImportError:
    tb_summary = None


class TensorBoardWriter(object):
    """Write events in TensorBoard format."""

    def __init__(self, logdir):
        if tb_summary is None:
            raise ValueError(
                "You must install TensorFlow " +
                "to use Tensorboard summary writer.")
        self._writer = tb_summary.FileWriter(logdir)

    def add(self, step, key, value):
        summary = tb_summary.Summary()
        summary_value = summary.value.add()
        summary_value.tag = key
        summary_value.simple_value = value
        self._writer.add_summary(summary, global_step=step)

    def flush(self):
        self._writer.flush()

    def close(self):
        self._writer.close()


class Reporter(object):
    """Manages reporting of metrics."""

    def __init__(self, log_interval=10, logdir=None, smooth_interval=10):
        self._writer = None
        if logdir:
            self._writer = TensorBoardWriter(logdir)
        self._last_step = 0
        self._last_reported_step = None
        self._last_reported_time = None
        self._log_interval = log_interval
        self._smooth_interval = smooth_interval
        self._metrics = collections.defaultdict(collections.deque)

    def record(self, step, **kwargs):
        for key, value in six.iteritems(kwargs):
            self.add(step, key, value)

    def add(self, step, key, value):
        self._last_step = step
        self._metrics[key].append(value)
        if len(self._metrics[key]) > self._smooth_interval:
            self._metrics[key].popleft()
        if self._last_step % self._log_interval == 0:
            if self._writer:
                self._writer.add(step, key, value)

    def report(self, stdout=None):
        if self._last_step % self._log_interval == 0:
            def smooth(values):
                return (sum(values) / len(values)) if values else 0.0
            metrics = ','.join(["%s = %.5f" % (k, smooth(v))
                                for k, v in six.iteritems(self._metrics)])
            if self._last_reported_time:
                elapsed_secs = time.time() - self._last_reported_time
                metrics += " (%.3f sec)" % elapsed_secs
                if self._writer:
                    elapsed_steps = float(
                        self._last_step - self._last_reported_step)
                    self._writer.add(
                        self._last_step, 'step/sec',
                        elapsed_steps / elapsed_secs)

            line = u"Step {}: {}".format(self._last_step, metrics)
            if stdout:
                stdout.write(line)
            else:
                print(line)

            self._last_reported_time = time.time()
            self._last_reported_step = self._last_step
