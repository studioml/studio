import tensorflow as tf

s = tf.Session()

x = tf.constant([1.0, 2.0])
y = x * 2

print(s.run(y))


