import unittest
import numpy as np
import urllib

from PIL import Image
from io import BytesIO

import keras
from keras.layers import Dense, Conv2D, Flatten

from keras.models import Sequential
from keras.datasets import mnist
from keras.utils import to_categorical

from timeout_decorator import timeout
from Queue import Queue, Full, Empty

from studio import model_util

class ModelUtilTest(unittest.TestCase):
    _multiprocess_can_split = True

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
        model = Sequential()
        model.add(Dense(2, input_shape=(2,)))
    

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
        
        
class BufferedPipeTest(unittest.TestCase):
    def test_pipe_simple(self):
        p = model_util.BufferedPipe() \
            .add(lambda x: x+1) \
            .add(lambda x: x*x) 

        l = list(p((x for x in range(1,5))))

        expected_l = [4, 9, 16, 25]

        self.assertEquals(l, expected_l)
        

    def test_pipe_buffer(self):
        p = model_util.BufferedPipe() \
            .add(lambda x: x+1, num_workers=32) \
            .add(lambda x: x*x) 

        out_gen = p((x for x in range(1,5)))

        expected_l = [4, 9, 16, 25]

        self.assertEquals(list(out_gen), expected_l)



class ModelPipeTest(unittest.TestCase):
    _multiprocess_can_split = True

    def test_model_pipe(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x*x, num_workers=32)


        input_dict = {x:x for x in range(10)}
        output_dict = p(input_dict)

        expected_dict = {k:v*v for k,v in input_dict.iteritems()}

        self.assertEquals(expected_dict, output_dict)
        
    @timeout(10)
    def test_model_pipe_long(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x*x, num_workers=32)


        input_dict = {x:x for x in range(10000)}
        output_dict = p(input_dict)

        expected_dict = {k:v*v for k,v in input_dict.iteritems()}

        self.assertEquals(expected_dict, output_dict)

    def test_model_pipe_ordered(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x*x, num_workers=32)


        input_list = range(10)
        output_list = p.apply_ordered(input_list)

        expected_list = [x*x for x in input_list]

        self.assertEquals(expected_list, output_list)

    def test_model_pipe_batch(self):

        p = model_util.ModelPipe()
        p.add(lambda b: [x*x for x in b], batch_size=4)


        input_list = range(10)
        output_list = p.apply_ordered(input_list)

        expected_list = [x*x for x in input_list]

        self.assertEquals(expected_list, output_list)

    def test_model_pipe_exception(self):

        p = model_util.ModelPipe()
        p.add(lambda x: 1.0 / x, num_workers=4)


        input_list = range(-10,10)
        output_list = p.apply_ordered(input_list)

        expected_list = [1.0 / x if x != 0 else None for x in input_list]

        self.assertEquals(expected_list, output_list)



    def test_model_pipe_keras(self):

        model = keras.models.Sequential()
        model.add(keras.layers.Flatten(input_shape=(1,28,28)))
        model.add(keras.layers.Dense(128, activation='relu'))
        model.add(keras.layers.Dense(10, activation='softmax'))

        p = model_util.ModelPipe()
        #p.add(lambda url: urllib.readurl(url), num_workers=32)
        #p.add(lambda img_bytes: ImageIO(img_bytes))
        #p.add(model_util.reshape_image_to_input(model))
        
        input_data = [np.random.random((1,1,28,28)) for _ in range(2)]

        p.add(model.predict, batch_size=64, batcher=np.vstack)
        #p.add(model.predict)
        
        expected_output = [model.predict(x.reshape((1,1,28,28))) for x in input_data] 
        output = p.apply_ordered(input_data)
        
        self.assertTrue(np.isclose(np.array(output).flatten(), 
                                   np.array(expected_output).flatten()).all())


    
    def test_model_pipe_mnist_urls(self): 

        (x_train, y_train), (x_test, y_test) = mnist.load_data()

        x_train = x_train.reshape(60000, 28, 28, 1)
        x_test = x_test.reshape(10000, 28, 28, 1)
        x_train = x_train.astype('float32')
        x_test = x_test.astype('float32')
        x_train /= 255
        x_test /= 255

        y_train = to_categorical(y_train, 10)
        y_test = to_categorical(y_test, 10)

        model = Sequential()

        #model.add(Conv2D(32, 5, activation='relu', input_shape=(28,28,1), data_format='channels_last'))
        #model.add(Conv2D(64, 3, activation='relu'))
        #model.add(Flatten())
        model.add(Flatten(input_shape=(28,28,1)))
        model.add(Dense(128, activation='relu'))
        model.add(Dense(128, activation='relu'))

        model.add(Dense(10, activation='softmax'))

        no_epochs=3
        batch_size=32

        model.compile(loss='categorical_crossentropy', optimizer='adam')
        
        
        model.fit(
            x_train, y_train, validation_data=(
                x_test,
                y_test),
            epochs=no_epochs,
            batch_size=batch_size)
        


        pipe = model_util.ModelPipe()
               
        pipe.add(lambda url: urllib.urlopen(url).read())
        pipe.add(lambda img: Image.open(BytesIO(img)))
        pipe.add(model_util.resize_to_model_input(model))
        pipe.add(lambda t: model.predict(t), num_workers=1)
        pipe.add(np.argmax)

        url5 = 'http://blog.otoro.net/assets/20160401/png/mnist_output_10.png'
        url2 = 'http://joshmontague.com/images/mnist-2.png'
        urlb = 'http://joshmontague.com/images/mnist-3.png'

        #import pdb
        #pdb.set_trace()

        #output = pipe({url5:url5, url2:url2, urlb:urlb})
        output = pipe.apply_ordered([url5])

        print output


        



if __name__ == "__main__":
    unittest.main()
