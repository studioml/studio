import os
from . import fs_tracker, logs
import uuid
import glob
import time
import filelock

_local_queue_lock = filelock.FileLock(
    os.path.expanduser('~/.studioml/local_queue.lock')
)


class LocalQueue:
    def __init__(self, path=None, verbose=10):
        if path is None:
            self.path = fs_tracker.get_queue_directory()
        else:
            self.path = path
        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

    def has_next(self):
        return any(glob.glob(self.path + '/*'))

    def clean(self, timeout=0):
        while self.has_next():
            self.dequeue()

    # Delete and clean are the same for local queue
    def delete(self):
        self.clean()

    def dequeue(self, acknowledge=True, timeout=0):
        wait_step = 1
        for waited in range(0, timeout + wait_step, wait_step):
            with _local_queue_lock:
                files = glob.glob(self.path + '/*')
                if any(files):
                    first_file = min([(p, os.path.getmtime(p)) for p in files],
                                     key=lambda t: t[1])[0]

                    with open(first_file, 'r') as f:
                        data = f.read()

                    self.acknowledge(first_file)
                    if not acknowledge:
                        return data, first_file
                    else:
                        return data

                elif waited == timeout:
                    return None

            self.logger.info(
                ('No messages found, sleeping for {} ' +
                 ' (total sleep time {})').format(wait_step, waited))
            time.sleep(wait_step)

    def enqueue(self, data):
        with _local_queue_lock:
            filename = os.path.join(self.path, str(uuid.uuid4()))
            with open(filename, 'w') as f:
                f.write(data)

    def acknowledge(self, key):
        try:
            os.remove(key)
        except BaseException:
            pass

    def hold(self, key, minutes):
        self.acknowledge(key)

    def get_name(self):
        return 'local'


def get_local_queue_lock():
    return _local_queue_lock
