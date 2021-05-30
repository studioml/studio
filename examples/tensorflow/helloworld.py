import time
import logging
import tensorflow as tf


s = tf.Session()

x = tf.constant([1.0, 2.0])
y = x * 2

logging.basicConfig()
logger = logging.get_logger('helloworld')
logger.setLevel(10)

while True:
    logger.info(s.run(y))
    time.sleep(10)
