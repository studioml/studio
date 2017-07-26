import types
try:
    import keras
except ImportError:
    keras = None

import logging

from Queue import Full,Empty, Queue
from multiprocessing import Process
from threading import Thread
import numpy as np


logging.basicConfig()


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
                return filtered_output
            elif isinstance(data, types.ListType):
                return [el for el in filtered_output]
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


def _q2q_batch(func, queue_in, queue_out, filt=lambda x: True, batch_size=32, timeout=1):
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

        batch = [el for el in batch if filt(el)]

        retval = func(batch)
                
        for el in retval:
            put_success = False
            while not put_success:
                try:
                    queue_out.put_nowait(el)
                    put_success = True
                except Full:
                    pass

def _q2q_single(func, queue_in, queue_out, filt=lambda x: True, timeout=1):
    _q2q_batch(lambda b: [func(x) for x in b], queue_in, queue_out, filt, 1, timeout) 

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

def _q2gen(queue, timeout=5):
    while True:
        try:
            yield queue.get(True, timeout=timeout)
        except Empty:
            raise StopIteration


