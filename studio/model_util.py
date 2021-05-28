import types
try:
    import keras
    from keras.preprocessing import image as image_prep
except ImportError:
    keras = None

from studio.util import logs

from PIL import Image

try:
    from Queue import Full, Empty, Queue
except ImportError:
    from queue import Full, Empty, Queue

from threading import Thread
import numpy as np
import itertools
import six


class BufferedPipe:
    def __init__(self,
                 func=lambda x: x,
                 parent=None,
                 q_in=None,
                 q_out=None,
                 num_workers=0,
                 q_size=None,
                 batch_size=1,
                 filterf=lambda x: x is not None,
                 batcher=lambda x: x,
                 timeout=1):

        min_q_size = 10

        self.func = func
        self.parent = parent
        self.num_workers = num_workers
        self.filterf = filterf
        self.batch_size = batch_size
        self.batcher = batcher

        if num_workers > 0:
            self.q_size = q_size if q_size else 2 * num_workers

        self.q_out = q_out
        self.q_in = q_in
        self.q_size = max(min_q_size, 2 * num_workers)

        self.logger = logs.get_logger('BufferedPipe')
        self.logger.setLevel(10)
        self.timeout = timeout
        self.worker_frame = Thread

    def __call__(self, data_gen):
        if self.parent:
            data_gen = self.parent(data_gen)

        if self.num_workers == 0 and \
           self.batch_size == 1 and \
           self.q_in is None and \
           self.q_out is None:
            return (self._wrapped_func(x) for x in data_gen)

        q_in = self.q_in
        if q_in is None:
            q_in = Queue(self.q_size)
            Thread(target=_gen2q,
                   args=(data_gen, q_in),
                   ).start()

        q_out = self.q_out
        if q_out is None:
            q_out = Queue(self.q_size)

        if self.batch_size == 1:
            target = _q2q_single
            kwargs = {
                "func": self._wrapped_func,
                "queue_in": q_in,
                "queue_out": q_out,
                "filterf": self._wrapped_filter,
                "timeout": self.timeout}
        else:
            target = _q2q_batch
            kwargs = {
                "func": self._wrapped_func,
                "queue_in": q_in,
                "queue_out": q_out,
                "filterf": self._wrapped_filter,
                "batch_size": self.batch_size,
                "timeout": self.timeout}

        if self.num_workers == 0:
            self.worker_frame(target=target, kwargs=kwargs).start()
        else:
            for i in range(self.num_workers):
                self.worker_frame(target=target,
                                  kwargs=kwargs).start()

        if self.q_out is None:
            return _q2gen(q_out, timeout=self.timeout)

    def add(self, func,
            num_workers=None,
            batch_size=None,
            filterf=None,
            batcher=None,
            timeout=None):

        if num_workers is None and \
           batch_size is None and \
           filterf is None and \
           batcher is None and \
           timeout is None:
            g = self.func
            self.func = lambda x: func(g(x))
            return self
        else:
            assert self.q_out is None
            self.q_out = Queue(self.q_size)
            return BufferedPipe(
                func, self,
                q_in=self.q_out,
                num_workers=num_workers if num_workers else self.num_workers,
                batch_size=batch_size if batch_size else self.batch_size,
                filterf=filterf if filterf else self.filterf,
                batcher=batcher if batcher else self.batcher,
                timeout=timeout if timeout else self.timeout)

    def _wrapped_func(self, x):
        if isinstance(x, tuple):
            try:
                return (x[0], self.func(x[1]))
            except BaseException as e:
                self.logger.warning('Applying function to {} raised exception {}'
                                 .format(x[1], str(e)))
                self.logger.exception(e)
                return (x[0], None)

        elif isinstance(x, list) and isinstance(x[0], tuple):
            batch_index = [el[0] for el in x]
            batch_input = self.batcher([el[1] for el in x])
            try:
                batch_output = self.func(batch_input)
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                                 .format(batch_input, str(e)))
                self.logger.exception(e)
                batch_output = [None] * len(batch_index)

            try:
                return zip(batch_index, batch_output)
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                                 .format(x, str(e)))
                self.logger.exception(e)
                return None

        else:
            try:
                return self.func(x)
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                                 .format(x, str(e)))
                self.logger.exception(e)
                return None

    def _wrapped_filter(self, x):
        if isinstance(x, tuple):
            return self.filterf(x[1])
        else:
            return self.filterf(x)


class ModelPipe:
    def __init__(self):
        self._pipe = BufferedPipe()

    def add(self, func,
            num_workers=None,
            batch_size=None,
            filterf=None,
            batcher=None,
            timeout=None):
        if keras and (isinstance(func, keras.models.Sequential) or
                      isinstance(func, keras.models.Model)):
            model = func
            _prime_keras_model(func)
            func = model.predict

        self._pipe = self._pipe.add(
            func,
            num_workers,
            batch_size=batch_size,
            filterf=filterf,
            batcher=batcher,
            timeout=timeout)
        return self

    def apply_unordered(self, data):

        if not isinstance(data, dict):
            count_gen = itertools.count(start=0, step=1)
            indexed_gen = six.moves.zip(count_gen, (x for x in data))
        else:
            indexed_gen = ((k, v) for k, v in six.iteritems(data))

        output_gen = self._pipe(indexed_gen)

        if isinstance(data, list):
            return [x for x in output_gen]
        elif isinstance(data, types.GeneratorType):
            return output_gen
        elif isinstance(data, dict):
            return {x[0]: x[1] for x in output_gen}
        elif isinstance(data, set):
            return {x[1] for x in output_gen}

    def apply_ordered(self, data):
        unordered = self.apply_unordered(data)
        if isinstance(data, dict) or \
           isinstance(data, set):
            return unordered
        elif isinstance(data, list):
            return [x[1] for x in sorted(unordered, key=lambda x:x[0])]
        elif isinstance(data, types.GeneratorType):
            return (x[1] for x in sorted(unordered, key=lambda x: x[0]))

    def __call__(self, data):
        return self.apply_unordered(data)


def resize_to_model_input(model, input_index=0):
    assert keras is not None
    assert isinstance(
        model, keras.models.Model) or isinstance(
        model, keras.models.Sequential)

    input_shape = tuple(
        [x.value for x in model.inputs[input_index].shape if x.value])
    assert len(input_shape) == 3

    if len(input_shape) == 3:
        assert input_shape[0] == 1 or input_shape[2] == 1 or \
            input_shape[0] == 3 or input_shape[2] == 3

        if input_shape[0] == 1 or input_shape[0] == 3:
            data_format = 'channels_first'
        else:
            data_format = 'channels_last'

    def _run_resize(input_img):
        if input_img is None:
            return None
        if len(input_shape) == 3:
            img = input_img.resize(
                (input_shape[1], input_shape[0]), Image.ANTIALIAS)

        arr = image_prep.img_to_array(img, data_format)
        arr /= 255.0

        if input_shape[0] == 1 and arr.shape[0] > 1:
            arr = np.mean(arr, axis=0)

        if input_shape[2] == 1 and arr.shape[2] > 1:
            arr = np.mean(arr, axis=2)

        return arr.reshape((1,) + input_shape)

    return _run_resize


def _q2q_batch(
        func,
        queue_in,
        queue_out,
        filterf=lambda x: x is not None,
        batch_size=32,
        timeout=1):
    while True:
        added = 0
        batch = []
        while True:
            try:
                if added > 0:
                    next_el = queue_in.get_nowait()
                else:
                    next_el = queue_in.get(True, timeout)

                if filterf(next_el):
                    batch.append(next_el)
                    added += 1

                if added == batch_size:
                    break
            except Empty:
                break

        if not any(batch):
            return

        retval = func(batch)

        for el in retval:
            put_success = False
            while not put_success:
                try:
                    queue_out.put_nowait(el)
                    put_success = True
                except Full:
                    pass


def _q2q_single(func, queue_in, queue_out, filterf=lambda x: True, timeout=1):
    _q2q_batch(
        lambda b: [
            func(x) for x in b],
        queue_in,
        queue_out,
        filterf,
        1,
        timeout)


def _gen2q(data, queue):
    while True:
        try:
            next_el = next(data)
        except StopIteration:
            return

        enqueued_successfully = False
        while not enqueued_successfully:
            try:
                queue.put_nowait(next_el)
                enqueued_successfully = True
            except Full:
                pass


def _q2gen(queue, timeout=1):
    while True:
        try:
            yield queue.get(True, timeout=timeout)
        except Empty:
            raise StopIteration


def _prime_keras_model(model):
    input_shapes = [[s.value if s.value else 1 for s in l.shape]
                    for l in model.inputs]
    dummy_inputs = [np.random.random(shape) for shape in input_shapes]

    model.predict(dummy_inputs)
