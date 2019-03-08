import time
from studio import logs

logger = logs.getLogger('helloworld')
logger.setLevel(10)

i = 0
while True:
    logger.info('{} seconds passed '.format(i))
    time.sleep(1)
    i += 1
