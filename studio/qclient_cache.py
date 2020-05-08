import threading

from .rabbit_queue import RMQueue

_queue_cache = {}

def get_cached_queue(
        name,
        route,
        cloud=None,
        config=None,
        logger=None,
        close_after=None,
        verbose=10):

    q = _queue_cache.get(name, None)
    if q is not None:
        if logger is not None:
            logger.info("Got queue named {0} from queue cache."
                        .format(name))
        return q

    q = RMQueue(
        queue=name,
        route=route,
        config=config,
        logger=logger,
        verbose=verbose)

    if logger is not None:
        logger.info("Created new queue named {0}.".format(name))

    if close_after is not None and close_after.total_seconds() > 0:
        thr = threading.Timer(
            interval=close_after.total_seconds(),
            function=purge_rmq,
            kwargs={
                "q": q,
                "logger": logger})
        thr.setDaemon(True)
        thr.start()

    _queue_cache[name] = q
    if logger is not None:
        logger.info("Added queue named {0} to queue cache."
                    .format(name))
    return q

def shutdown_cached_queue(queue, logger=None, delete_queue=True):
    if queue is None:
        return

    _queue_cache.pop(queue.get_name(), None)
    if logger is not None:
        logger.info("Removed queue named {0} from queue cache."
                    .format(queue.get_name()))

    queue.shutdown(delete_queue)


def purge_rmq(q, logger, **kwargs):
    if q is None:
        return

    try:
        q.shutdown(True)
    except BaseException as e:
        logger.warning(e)
        return
    return
