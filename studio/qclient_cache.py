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
    if queue_cache.get(name, None) is None:
	queue_cache[name] = RMQueue(
	    queue=name,
	    route=route,
	    config=config,
	    logger=logger,
	    verbose=verbose)
    return queue_cache[name]
