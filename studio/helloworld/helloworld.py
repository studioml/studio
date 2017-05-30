import tensorflow as tf
import time
import studio
import logging


s = tf.Session()

x = tf.constant([1.0, 2.0])
y = x * 2

logging.basicConfig()

logger = logging.getLogger('helloworld')
logger.setLevel(10)

while True:
    logger.info(s.run(y))
    with open(studio.get_model_directory() + "a.txt", "w") as f:
        f.write('111')

    time.sleep(10)
