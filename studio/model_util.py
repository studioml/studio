import types
try:
    import keras
    from keras.preprocessing import image as image_prep
except ImportError:
    keras = None

import logging

from PIL import Image

from Queue import Full,Empty
from multiprocessing import Process, Queue
from threading import Thread
import numpy as np
import itertools 


logging.basicConfig()

class BufferedPipe:
    def __init__(self, 
                 func=lambda x:x, 
                 parent=None,
                 q_in=None,
                 q_out=None,
                 num_workers=0,
                 q_size=10,
                 batch_size=1,
                 filterf=lambda x:x is not None,
                 batcher=lambda x:x):


        self.func = func
        self.parent = parent
        self.num_workers = num_workers
        self.filterf = filterf
        self.batch_size = batch_size
        self.batcher = batcher

        if num_workers > 0:
            self.q_size = q_size if q_size else 2*num_workers

        self.q_out = q_out
        self.q_in = q_in
        self.q_size = q_size
        
        self.logger = logging.getLogger('BufferedPipe')
        self.logger.setLevel(10)
        self.timeout = 10
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
                "func":self._wrapped_func, 
                "queue_in":q_in, 
                "queue_out":q_out,
                "filterf":self.filterf,
                "timeout":self.timeout}
        else:
            target = _q2q_batch
            kwargs = {
                "func":self._wrapped_func, 
                "queue_in":q_in, 
                "queue_out":q_out,
                "filterf":self.filterf, 
                "batch_size":self.batch_size,
                "timeout":self.timeout}

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
            batcher=None):

        if num_workers == 0:
            g = self.func
            self.func = lambda x: func(g(x))
            self.batch_size = batch_size
            self.batcher = batcher
            return self

        if num_workers is None and \
           batch_size is None and \
           filterf is None and \
           batcher is None:
               g = self.func
               self.func = lambda x: func(g(x))
        else:
            assert self.q_out is None
            self.q_out = Queue(self.q_size)
            return BufferedPipe(
                    func, self, 
                    q_in=self.q_out, 
                    num_workers=num_workers if num_workers else self.num_workers, 
                    batch_size=batch_size if batch_size else self.batch_size, 
                    filterf=filterf if filterf else self.filterf,
                    batcher=batcher if batcher else self.batcher)

    def _wrapped_func(self, x):
        if isinstance(x, tuple):
            try:
                return (x[0], self.func(x[1]))
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                        .format(x[1], e.message))
                self.logger.exception(e)
                return (x[0], None)

        elif isinstance(x, list) and isinstance(x[0], tuple):
            batch_index = [el[0] for el in x]
            batch_input = self.batcher([el[1] for el in x])
            try:
                batch_output = self.func(batch_input)
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                        .format(batch_input, e.message))
                self.logger.exception(e)
                batch_output = [None] * len(batch_index)

            return zip(batch_index, batch_output)

        else:
            try:
                return self.func(x)
            except BaseException as e:
                self.logger.warn('Applying function to {} raised exception {}'
                        .format(x, e.message))
                self.logger.exception(e)
                return None


class ModelPipe:
    def __init__(self):
        self._pipe = BufferedPipe()

    def add(self, func, num_workers=0, batch_size=1, filterf=lambda x: x is not None, batcher=lambda x:x):
        self._pipe = self._pipe.add(func, num_workers, batch_size=batch_size, filterf=filterf, batcher=batcher)
        return self

    def apply_unordered(self, data):

        if not isinstance(data, dict):
            count_gen = itertools.count(start=0, step=1)
            indexed_gen = itertools.izip(count_gen, (x for x in data))
        else:
            indexed_gen = ((k,v) for k,v in data.iteritems())
            
        output_gen = self._pipe(indexed_gen)

        if isinstance(data, list):
            return [x for x in output_gen]
        elif isinstance(data, types.GeneratorType):
            return output_gen
        elif isinstance(data, dict):
            return {x[0]:x[1] for x in output_gen}
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
            return (x[1] for x in sorted(unordered, key=lambda x:x[0]))

    def __call__(self, data):
        return self.apply_unordered(data)



class KerasModelWrapper:
    def __init__(self, model=None, checkpoint_name=None, 
                 model_transform=lambda x: x, 
                 preprocessing=lambda x: x,
                 postprocessing=lambda x: x):

        assert model is not None or checkpoint_name is not None, \
            "Either model or checkpoint_name should be specified!"

        if model is not None:
            self.model = model
        else:
            self.model = keras.models.load_model(checkpoint_name)

        self.model = model_transform(self.model)

        self.preprocessing = preprocessing
        self.postprocessing = postprocessing
        self.logger = logging.getLogger('KerasModelWrapper')
        self.logger.setLevel(10)

        self.threadpool = []
        self.processpool = []
        
        
    def __call__(self, data):
        if isinstance(data, types.DictType):

            output_gen = self._predict_generator(data_iteritems)
            return {el[0]:el[1] for el in output_gen}

        else:

            transformed_data = (self._wrapped_preprocessing(el) for el in data)
            inner_output = self._predict_generator(transformed_data)
            output_gen =  (self._wrapped_postprocessing(el) for el in inner_output)

            if isinstance(data, types.GeneratorType):
                return filterfed_output
            elif isinstance(data, types.ListType):
                return [el for el in filterfed_output]
            else:
                return output_gen.iter().next()




    def _predict_generator(self, data, prefetch_length=10, prefetch_workers=1):
        assert isinstance(data, types.GeneratorType)
        preprocessing_q = Queue(prefetch_length)
        prediction_q = Queue(prefetch_length)
        postprocessing_q = Queue(prefetch_length)
        results_q = Queue(prefetch_length)

        for i in range(prefetch_workers):
            Thread(target=_gen2q, args=(data, preprocessing_q)).start()

        
        #for i in range(prefetch_workers):
        #    Thread(target=_q2q_single,
        #            args = (
        #                self._wrapped_preprocessing,
        #                preprocessing_q,
        #                prediction_q)).start()


        def predict_on_batch(b):
            try:
                return self.model.predict(np.array([x[1][0] for x in b]))
            except BaseException as e:
                self.logger.error('prediction on batch raised exception {}'
                        .format(e.message))
                self.logger.exception(e)
                return [None] * len(b)


        t = Thread(target=_q2q_batch,
                args=(
                    predict_on_batch, 
                    preprocessing_q, 
                    results_q,
                    lambda x: x[1] is not None ))
        t.start()
        #t.join()


        #_q2q_batch(predict_on_batch, preprocessing_q, results_q, lambda x: x[1] is not None)

        #for i in range(prefetch_workers):
        #    Thread(target=_q2q_single,
        #            args = (self._wrapped_postprocessing, 
        #                    postprocessing_q, 
        #                    results_q)).start()
                
        ret_gen = _q2gen(results_q)

        return ret_gen
                     

    def _wrapped_preprocessing(self,data):
        try:
            return self.preprocessing(data)
        except BaseException as e:
            logger.error('Exception {} was caught while preprocessing'
                    .format(e.message))
            return None
            
    def _wrapped_postprocessing(self, data):
        try:
            return self.postprocessing(data)
        except BaseException as e:
            logger.error('Exception {} was caught while postprocessing'
                    .format(e.message))
            return None

    def get_model(self):
        return self.model




class TensorFlowModelWrapper:
    def __init__(self):
        raise NotImplementedError

    def __call__(self, data):
        raise NotImplementedError


def resize_to_model_input(model, input_index=0):

    input_shape = tuple([x.value for x in model.inputs[input_index].shape if x.value])
    assert keras is not None
    assert len(input_shape) == 3 

    if len(input_shape) == 3:  
        assert input_shape[0] == 1 or input_shape[2] == 1 or \
               input_shape[0] == 3 or input_shape[2] == 3

        if input_shape[0] == 1 or input_shape[0] == 3:
            data_format = 'channels_first'
        else:
            data_format = 'channels_last'


    def _run_resize(input_img):
        #assert instanceof(image, Image)
        if len(input_shape) == 3:
            img = input_img.resize((input_shape[1], input_shape[0]), Image.ANTIALIAS)
       
        arr = image_prep.img_to_array(img, data_format)
        arr /= 255.0

        if input_shape[0] == 1 and arr.shape[0] > 1:
            arr = np.mean(arr, axis=0)

        if input_shape[2] == 1 and arr.shape[2] > 1:
            arr = np.mean(arr, axis=2)

        return arr.reshape((1,) + input_shape)
    
    return _run_resize




def _q2q_batch(func, queue_in, queue_out, filterf=lambda x: True, batch_size=32, timeout=1):
    while True:
        try:
            batch = [queue_in.get(True, timeout)]
        except Empty:
            return

        for i in range(1,batch_size):
            try:
                batch.append(queue_in.get_nowait())
            except Empty:
                break

        batch = [el for el in batch if filterf(el)]

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
    _q2q_batch(lambda b: [func(x) for x in b], queue_in, queue_out, filterf, 1, timeout) 

def _gen2q(data, queue):
    while True:
        try:
            next_el = data.next()
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


