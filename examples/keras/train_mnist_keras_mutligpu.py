import sys
from keras.layers import Input, Dense
from keras.models import Model
from keras.datasets import mnist
from keras.utils import to_categorical
from keras.callbacks import ModelCheckpoint, TensorBoard

from studio import fs_tracker
from studio import multi_gpu

# this placeholder will contain our input digits, as flat vectors
img = Input((784,))
# fully-connected layer with 128 units and ReLU activation
x = Dense(128, activation='relu')(img)
x = Dense(128, activation='relu')(x)
# output layer with 10 units and a softmax activation
preds = Dense(10, activation='softmax')(x)


no_gpus = 2
batch_size = 128

model = Model(img, preds)
model = multi_gpu.make_parallel(model, no_gpus)
model.compile(loss='categorical_crossentropy', optimizer='adam')

(x_train, y_train), (x_test, y_test) = mnist.load_data()

x_train = x_train.reshape(60000, 784)
x_test = x_test.reshape(10000, 784)
x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
x_train /= 255
x_test /= 255

# convert class vectors to binary class matrices
y_train = to_categorical(y_train, 10)
y_test = to_categorical(y_test, 10)


checkpointer = ModelCheckpoint(
    fs_tracker.get_model_directory() +
    '/checkpoint.{epoch:02d}-{val_loss:.2f}.hdf')


tbcallback = TensorBoard(log_dir=fs_tracker.get_tensorboard_dir(),
                         histogram_freq=0,
                         write_graph=True,
                         write_images=False)


model.fit(
    x_train,
    y_train,
    validation_data=(x_test, y_test),
    epochs=int(sys.argv[1]),
    batch_size=batch_size * no_gpus,
    callbacks=[checkpointer, tbcallback])
