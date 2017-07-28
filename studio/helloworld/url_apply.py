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

'''
model.fit(
    x_train, y_train, validation_data=(
    x_test,
    y_test),
    epochs=no_epochs,
    batch_size=batch_size)
'''


pipe = model_util.ModelPipe()
       
pipe.add(lambda url: urllib.urlopen(url).read())
pipe.add(lambda img: Image.open(BytesIO(img)))
pipe.add(model_util.resize_to_model_input(model))
pipe.add(lambda t: model.predict(t), num_workers=1)
pipe.add(np.argmax)

url5 = 'http://blog.otoro.net/assets/20160401/png/mnist_output_10.png'
url2 = 'http://joshmontague.com/images/mnist-2.png'
urlb = 'http://joshmontague.com/images/mnist-3.png'

output = pipe.apply_ordered([url5])
print(output)
