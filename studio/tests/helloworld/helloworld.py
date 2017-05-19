import tensorflow as tf
import time

s = tf.Session()

x = tf.constant([1.0, 2.0])
y = x * 2

while True:
    print(s.run(y))
    time.sleep(10)



