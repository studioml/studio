Distributed
===========

TensorFlow
----------

To easily distribute your ML with Tensorflow, you should use `tf.estimators.Estimator` interface.

See `mnist-estimator.py <https://github.com/studioml/studio/blob/master/examples/tensorflow/mnist-estimator.py>`__ for the usage.

To run it distributedly:

::
        studio run --distributed=tensorflow --num_workers=4 --num_ps=1 mnist-estimator.py

