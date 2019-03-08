import sys

from studio import fs_tracker

from keras.layers import Dense, Flatten, Conv2D, BatchNormalization

from keras.models import Sequential
from keras.datasets import cifar10
from keras.utils import to_categorical

from keras import optimizers
from keras.callbacks import ModelCheckpoint, TensorBoard

import tensorflow as tf
from keras import backend as backend

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
sess = tf.Session(config=config)

backend.set_session(sess)

(x_train, y_train), (x_test, y_test) = cifar10.load_data()

x_train = x_train.reshape(50000, 32, 32, 3)
x_test = x_test.reshape(10000, 32, 32, 3)
x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
x_train /= 255
x_test /= 255

# convert class vectors to binary class matrices
y_train = to_categorical(y_train, 10)
y_test = to_categorical(y_test, 10)


model = Sequential()

model.add(Conv2D(32, (5, 5), activation='relu', input_shape=(32, 32, 3)))
model.add(Conv2D(32, (3, 3), activation='relu'))
model.add(BatchNormalization())
model.add(Conv2D(64, (5, 5), activation='relu'))
model.add(Conv2D(64, (3, 3), activation='relu'))
model.add(BatchNormalization())
model.add(Conv2D(128, (3, 3), activation='relu'))
model.add(Conv2D(128, (3, 3), activation='relu'))
model.add(BatchNormalization())
model.add(Flatten())
model.add(Dense(10, activation='softmax'))
model.summary()


batch_size = 128
no_epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
lr = 0.01

print('learning rate = {}'.format(lr))
print('batch size = {}'.format(batch_size))
print('no_epochs = {}'.format(no_epochs))

model.compile(loss='categorical_crossentropy', optimizer=optimizers.SGD(lr=lr),
              metrics=['accuracy'])


checkpointer = ModelCheckpoint(
    fs_tracker.get_model_directory() +
    '/checkpoint.{epoch:02d}-{val_loss:.2f}.hdf')


tbcallback = TensorBoard(log_dir=fs_tracker.get_tensorboard_dir(),
                         histogram_freq=0,
                         write_graph=True,
                         write_images=True)


model.fit(
    x_train, y_train, validation_data=(
        x_test,
        y_test),
    epochs=no_epochs,
    callbacks=[checkpointer, tbcallback],
    batch_size=batch_size)
