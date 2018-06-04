from cachetools import LRUCache

from .rabbit_queue import RMQueue

queue_cache = {}


def get_cached_queue(
        name,
        cloud,
        route,
        config=None,
        logger=None,
        verbose=10):
    q = queue_cache.get(name, None)
    if q is not None:
        return q
    q = RMQueue(
        queue=name,
        route=route,
        config=config,
        logger=logger,
        verbose=verbose)
    queue_cache[name] = q
    return q
