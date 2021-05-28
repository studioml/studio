import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
ERROR = logging.ERROR

logging.basicConfig(
    format='%(asctime)s %(levelname)-6s %(name)s - %(message)s',
    level=ERROR,
    datefmt='%Y-%m-%d %H:%M:%S')


def get_logger(name):
    return logging.getLogger(name)


def debug(line):
    return logging.debug(line)


def error(line):
    return logging.error(line)


def info(line):
    return logging.info(line)
