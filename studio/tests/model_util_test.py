import unittest
import numpy as np
import keras
from studio import model_util
from Queue import Queue, Full, Empty

class ModelUtilTest(unittest.TestCase):

    def test_q2q_batch(self):
        data = range(10)
        q_in = Queue()
        q_out = Queue()
        
        for d in data:
            q_in.put(d)
       
        model_util._q2q_batch(lambda b: [x*x for x in b], q_in, q_out, batch_size=4)

        expected_out = [x*x for x in data] 
        actual_out = []
        while True:
            try:
                actual_out.append(q_out.get(True, 1))
            except Empty:
                break

        self.assertEquals(expected_out, actual_out)

    def test_q2q_batch_filter(self):
        data = range(10)
        q_in = Queue()
        q_out = Queue()
        
        for d in data:
            q_in.put(d)
       
        model_util._q2q_batch(lambda b: [x*x for x in b], q_in, q_out, filt=lambda x: x != 3, batch_size=4)

        expected_out = [x*x for x in data if x != 3] 
        actual_out = []
        while True:
            try:
                actual_out.append(q_out.get(True, 1))
            except Empty:
                break

        self.assertEquals(expected_out, actual_out)


    def test_q2gen_gen2q(self):
        data = (x for x in range(10))
        q = Queue()

        model_util._gen2q(data, q)

        expected_out = range(10)
        actual_out = []
        while True:
            try:
                actual_out.append(q.get(True, 1))
            except Empty:
                break
 
        self.assertEquals(expected_out, actual_out)


        model_util._gen2q((x for x in range(10)), q)
        gen = model_util._q2gen(q)

        self.assertEquals(expected_out, list(gen))


    def test_predict_generator(self):
        model = keras.models.Sequential()
        model.add(keras.layers.Dense(2, input_shape=(2,)))
    

        #weights = [np.array([[2, 0], [0, 2]])]
        #model.set_weights(weights)
        test_data = np.random.random((4,2))
        print(model.predict(test_data))

        mw = model_util.KerasModelWrapper(model)

        no_samples = 10
        data = [(x,test_data[x].reshape(1,2)) for x in range(len(test_data))]

        out_gen = mw._predict_generator((x for x in data))
        
        #import pdb
        #pdb.set_trace()
        for x in out_gen:
            print(x)
        
        

        




   

if __name__ == "__main__":
    unittest.main()
