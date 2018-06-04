from cachetools import LRUCache

from .rabbit_queue import RMQueue

queue_cache = {}


def get_cached_queue(
        name,
        route,
        cloud=None,
        config=None,
        logger=None,
        verbose=10):
    return RMQueue(
        queue=name,
        route=route,
        config=config,
        logger=logger,
        verbose=verbose)
