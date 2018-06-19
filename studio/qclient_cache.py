import threading

from datetime import timedelta

from cachetools import LRUCache
from .rabbit_queue import RMQueue

queue_cache = {}


def get_cached_queue(
        name,
        route,
        cloud=None,
        config=None,
        logger=None,
        close_after=timedelta(),
        verbose=10):
    # if queue_cache.get(name, None) is None:
    #    queue_cache[name] = RMQueue(
    #        queue=name,
    #        route=route,
    #        config=config,
    #        logger=logger,
    #        verbose=verbose)
    #
    # return queue_cache[name]
    q = RMQueue(
        queue=name,
        route=route,
        config=config,
        logger=logger,
        verbose=verbose)
    if close_after is not None and close_after.total_seconds() > 0:
        thr = threading.Timer(
            interval=close_after.total_seconds(),
            function=purge_rmq,
            kwargs={
                "q": q,
                "logger": logger})
        thr.setDaemon(True)
        thr.start()

    return q


def purge_rmq(q, logger, **kwargs):
    if q is None:
        return

    try:
        q.stop()
    except BaseException as e:
        logger.warning(e)
        return
    return
