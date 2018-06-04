from cachetools import LRUCache

from .rabbit_queue import RMQueue

queue_cache = {}


def get_cached_queue(
        name=None,
        cloud=None,
        route=None,
        config=None,
        logger=None,
        verbose=10):
    q = queue_cache.get(name, None)
    if q is not None:
        return q
    q = RMQueue(
        queue=queue,
        route=route,
        config=config,
        logger=logger,
        verbose=verbose)
    queue_cache[name] = q
    return q
