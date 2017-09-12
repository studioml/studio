"""Example of MNIST trained with Estimator (and supports distributed case)."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse

import numpy as np

import tensorflow as tf
from tensorflow.python.estimator.model_fn import ModeKeys as Modes
from tensorflow.examples.tutorials.mnist import input_data

import studio


tf.logging.set_verbosity(tf.logging.INFO)


def _cnn_model_fn(features, labels, mode):
  # Input Layer
  input_layer = tf.reshape(features['inputs'], [-1, 28, 28, 1])

  # Convolutional Layer #1
  conv1 = tf.layers.conv2d(
      inputs=input_layer,
      filters=32,
      kernel_size=[5, 5],
      padding='same',
      activation=tf.nn.relu)

  # Pooling Layer #1
  pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[2, 2], strides=2)

  # Convolutional Layer #2 and Pooling Layer #2
  conv2 = tf.layers.conv2d(
      inputs=pool1,
      filters=64,
      kernel_size=[5, 5],
      padding='same',
      activation=tf.nn.relu)
  pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[2, 2], strides=2)

  # Dense Layer
  pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
  dense = tf.layers.dense(inputs=pool2_flat, units=1024, activation=tf.nn.relu)
  dropout = tf.layers.dropout(
      inputs=dense, rate=0.4, training=(mode == Modes.TRAIN))

  # Logits Layer
  logits = tf.layers.dense(inputs=dropout, units=10)

  # Define operations
  if mode in (Modes.PREDICT, Modes.EVAL):
    predicted_indices = tf.argmax(input=logits, axis=1)
    probabilities = tf.nn.softmax(logits, name='softmax_tensor')

  if mode in (Modes.TRAIN, Modes.EVAL):
    global_step = tf.contrib.framework.get_or_create_global_step()
    loss = tf.losses.softmax_cross_entropy(
        onehot_labels=labels, logits=logits)
    tf.summary.scalar('OptimizeLoss', loss)

  if mode == Modes.PREDICT:
    predictions = {
        'classes': predicted_indices,
        'probabilities': probabilities
    }
    export_outputs = {
        'prediction': tf.estimator.export.PredictOutput(predictions)
    }
    return tf.estimator.EstimatorSpec(
        mode, predictions=predictions, export_outputs=export_outputs)

  if mode == Modes.TRAIN:
    optimizer = tf.train.AdamOptimizer(learning_rate=0.001)
    train_op = optimizer.minimize(loss, global_step=global_step)
    return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)

  if mode == Modes.EVAL:
    eval_metric_ops = {
        'accuracy': tf.metrics.accuracy(label_indices, predicted_indices)
    }
    return tf.estimator.EstimatorSpec(
        mode, loss=loss, eval_metric_ops=eval_metric_ops)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--train_steps', help='Steps to run the trianing job for.', 
        type=int, default=10000)
    parser.add_argument(
        '--batch_size', help='Batch size.', type=int, default=32)
    args = parser.parse_args()
    
    est = tf.estimator.Estimator(
      model_fn=_cnn_model_fn,
      model_dir=studio.fs_tracker.get_model_directory(),
      config=tf.contrib.learn.RunConfig(save_checkpoints_secs=180))

    mnist_data = input_data.read_data_sets('MNIST_data', one_hot=True)
    train_input_fn = tf.estimator.inputs.numpy_input_fn(
        x={'inputs': mnist_data.train.images},
        y=mnist_data.train.labels.astype(np.int32),
        batch_size=args.batch_size, shuffle=True)
    est.train(train_input_fn, steps=args.train_steps)

