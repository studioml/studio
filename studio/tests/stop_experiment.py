import time
import logging

logging.basicConfig()
logger = logging.getLogger('helloworld')
logger.setLevel(10)

i = 0
while True:
    logger.info('{} seconds passed '.format(i))
    time.sleep(1)
    i += 1
