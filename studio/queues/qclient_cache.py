import threading

from studio.queues.rabbit_queue import RMQueue
from studio.util.util import check_for_kb_interrupt

_queue_cache = {}

def get_cached_queue(
        name,
        route,
        config=None,
        logger=None,
        close_after=None):

    queue = _queue_cache.get(name, None)
    if queue is not None:
        if logger is not None:
            logger.info("Got queue named %s from queue cache.", name)
        return queue

    queue = RMQueue(
        queue=name,
        route=route,
        config=config,
        logger=logger)

    if logger is not None:
        logger.info("Created new queue named %s.", name)

    if close_after is not None and close_after.total_seconds() > 0:
        thr = threading.Timer(
            interval=close_after.total_seconds(),
            function=purge_rmq,
            kwargs={
                "q": queue,
                "logger": logger})
        thr.setDaemon(True)
        thr.start()

    _queue_cache[name] = queue
    if logger is not None:
        logger.info("Added queue named %s to queue cache.", name)
    return queue

def shutdown_cached_queue(queue, logger=None, delete_queue=True):
    if queue is None:
        return

    _queue_cache.pop(queue.get_name(), None)
    if logger is not None:
        logger.info("Removed queue named %s from queue cache.",
                    queue.get_name())

    queue.shutdown(delete_queue)


def purge_rmq(queue, logger):
    if queue is None:
        return

    try:
        queue.shutdown(True)
    except BaseException as exc:
        check_for_kb_interrupt()
        logger.warning(exc)
        return
    return
