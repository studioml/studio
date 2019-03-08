import tensorflow as tf


sess = tf.Session()
a = tf.constant([1.0, 5.0])
b = a + 1.0

result = sess.run(b)
assert len(result) == 2

print("[ {} {} ]".format(result[0], result[1]))
