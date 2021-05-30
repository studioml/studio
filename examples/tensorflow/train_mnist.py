import tensorflow as tf
import sys
import os
import time

from keras.objectives import categorical_crossentropy
from keras.layers import Dense
from tensorflow.examples.tutorials.mnist import input_data

from keras import backend as K
from studio import fs_tracker

import logging

logging.basicConfig()

sess = tf.Session()
K.set_session(sess)
# Now let's get started with our MNIST model. We can start building a
# classifier exactly as you would do in TensorFlow:

# this placeholder will contain our input digits, as flat vectors
img = tf.placeholder(tf.float32, shape=(None, 784))
# We can then use Keras layers to speed up the model definition process:


# Keras layers can be called on TensorFlow tensors:
# fully-connected layer with 128 units and ReLU activation
x = Dense(128, activation='relu')(img)
x = Dense(128, activation='relu')(x)
# output layer with 10 units and a softmax activation
preds = Dense(10, activation='softmax')(x)
# We define the placeholder for the labels, and the loss function we will use:

labels = tf.placeholder(tf.float32, shape=(None, 10))

loss = tf.reduce_mean(categorical_crossentropy(labels, preds))
# Let's train the model with a TensorFlow optimizer:

mnist_data = input_data.read_data_sets('MNIST_data', one_hot=True)

global_step = tf.Variable(0, name='global_step', trainable=False)
train_step = tf.train.GradientDescentOptimizer(
    0.5).minimize(loss, global_step=global_step)
# Initialize all variables
init_op = tf.global_variables_initializer()
saver = tf.train.Saver()
sess.run(init_op)


logger = logging.get_logger('train_mnist')
logger.setLevel(10)
# Run training loop
with sess.as_default():
    while True:
        batch = mnist_data.train.next_batch(50)
        train_step.run(feed_dict={img: batch[0],
                                  labels: batch[1]})

        sys.stdout.flush()
        saver.save(
            sess,
            os.path.join(
                fs_tracker.get_model_directory(),
                "ckpt"),
            global_step=global_step)
        time.sleep(1)
