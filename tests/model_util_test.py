import unittest
import numpy as np
import six

from PIL import Image
from io import BytesIO

try:
    import keras
    from keras.layers import Dense, Flatten
    from keras.models import Sequential
    from keras.datasets import mnist
    from keras.utils import to_categorical

except ImportError:
    keras = None

from timeout_decorator import timeout

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty
from studio import model_util


class ModelUtilTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def test_q2q_batch(self):
        data = six.moves.range(10)
        q_in = Queue()
        q_out = Queue()

        for d in data:
            q_in.put(d)

        model_util._q2q_batch(
            lambda b: [
                x * x for x in b],
            q_in,
            q_out,
            batch_size=4)

        expected_out = [x * x for x in data]
        actual_out = []
        while True:
            try:
                actual_out.append(q_out.get(True, 1))
            except Empty:
                break

        self.assertEquals(expected_out, actual_out)

    def test_q2q_batch_filter(self):
        data = six.moves.range(10)
        q_in = Queue()
        q_out = Queue()

        for d in data:
            q_in.put(d)

        model_util._q2q_batch(
            lambda b: [
                x * x for x in b],
            q_in,
            q_out,
            filterf=lambda x: x != 3,
            batch_size=4)

        expected_out = [x * x for x in data if x != 3]
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

        expected_out = list(range(10))
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


class BufferedPipeTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def test_pipe_simple(self):
        p = model_util.BufferedPipe() \
            .add(lambda x: x + 1) \
            .add(lambda x: x * x)

        lst = list(p((x for x in range(1, 5))))

        expected_l = [4, 9, 16, 25]

        self.assertEquals(lst, expected_l)

    @unittest.skip('ordering problem - peterz to fix')
    def test_pipe_buffer(self):
        p = model_util.BufferedPipe() \
            .add(lambda x: x + 1, num_workers=32) \
            .add(lambda x: x * x)

        out_gen = p((x for x in range(1, 5)))

        expected_l = [4, 9, 16, 25]

        self.assertEquals(list(out_gen), expected_l)


class ModelPipeTest(unittest.TestCase):
    _multiprocess_shared_ = True

    def test_model_pipe(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x * x, num_workers=32)

        input_dict = {x: x for x in range(10)}
        output_dict = p(input_dict)

        expected_dict = {k: v * v for k, v in six.iteritems(input_dict)}

        self.assertEquals(expected_dict, output_dict)

    @unittest.skip('peterz fix - fails in python3.6')
    @timeout(30)
    def test_model_pipe_long(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x * x, num_workers=32, timeout=0.5)

        input_dict = {x: x for x in range(10000)}
        output_dict = p(input_dict)

        expected_dict = {k: v * v for k, v in six.iteritems(input_dict)}

        self.assertEquals(expected_dict, output_dict)

    def test_model_pipe_ordered(self):

        p = model_util.ModelPipe()
        p.add(lambda x: x * x, num_workers=32)

        input_list = list(range(10))
        output_list = p.apply_ordered(input_list)

        expected_list = [x * x for x in input_list]

        self.assertEquals(expected_list, output_list)

    def test_model_pipe_batch(self):

        p = model_util.ModelPipe()
        p.add(lambda b: [x * x for x in b], batch_size=4)

        input_list = list(range(10))
        output_list = p.apply_ordered(input_list)

        expected_list = [x * x for x in input_list]

        self.assertEquals(expected_list, output_list)

    def test_model_pipe_exception(self):

        p = model_util.ModelPipe()
        p.add(lambda x: 1.0 / x, num_workers=4)

        input_list = list(range(-10, 10))
        output_list = p.apply_ordered(input_list)

        expected_list = [1.0 / x if x != 0 else None for x in input_list]

        self.assertEquals(expected_list, output_list)


@unittest.skipIf(keras is None,
                 "These tests require keras")
class KerasModelPipeTest(unittest.TestCase):
    def test_model_pipe_keras(self):
        model = Sequential()
        model.add(Flatten(input_shape=(1, 28, 28)))
        model.add(Dense(128, activation='relu'))
        model.add(Dense(10, activation='softmax'))

        p = model_util.ModelPipe()
        input_data = [np.random.random((1, 1, 28, 28)) for _ in range(2)]

        p.add(model.predict, batch_size=64, batcher=np.vstack)

        expected_output = [
            model.predict(
                x.reshape(
                    (1, 1, 28, 28))) for x in input_data]
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

        model.add(Flatten(input_shape=(28, 28, 1)))
        model.add(Dense(128, activation='relu'))
        model.add(Dense(128, activation='relu'))

        model.add(Dense(10, activation='softmax'))

        no_epochs = 3
        batch_size = 32

        model.compile(loss='categorical_crossentropy', optimizer='adam')

        model.fit(
            x_train, y_train, validation_data=(
                x_test,
                y_test),
            epochs=no_epochs,
            batch_size=batch_size)

        pipe = model_util.ModelPipe()

        pipe.add(
            lambda url: six.moves.urllib.request.urlopen(url).read(),
            num_workers=2,
            timeout=10)
        pipe.add(lambda img: Image.open(BytesIO(img)))
        pipe.add(model_util.resize_to_model_input(model))
        pipe.add(lambda x: 1 - x)
        pipe.add(model, num_workers=1, batch_size=32, batcher=np.vstack)
        pipe.add(lambda x: np.argmax(x, axis=1))

        url5 = 'http://blog.otoro.net/assets/20160401/png/mnist_output_10.png'
        url2 = 'http://joshmontague.com/images/mnist-2.png'
        urlb = 'http://joshmontague.com/images/mnist-3.png'

        expected_output = {url5: 5, url2: 2}
        output = pipe({url5: url5, url2: url2, urlb: urlb})
        output = {k: v for k, v in six.iteritems(output) if v}

        self.assertEquals(output, expected_output)


if __name__ == "__main__":
    unittest.main()
