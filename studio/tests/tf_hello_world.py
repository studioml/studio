import tensorflow as tf


sess = tf.Session()
a = tf.constant([1.0, 5.0])
b = a + 1.0

print(sess.run(b))
