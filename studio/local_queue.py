import os
import sys
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
        self.status_marker = os.path.join(self.path, 'is_active.queue')
        try:
            with open(self.status_marker, "w") as sm:
                pass
        except IOError as error:
            self.logger.error('FAILED to create {0} for LocalQueue. ABORTING.'
                              .format(self.status_marker))
            sys.exit(-1)

    def _get_queue_status(self):
        with _local_queue_lock:
            files = glob.glob(self.path + '/*')
            if files is None:
                files = list()
        is_active = self.status_marker in files
        try:
            files.remove(self.status_marker)
        except:
            # Ignore possible exception:
            # we just want list of files without status marker
            pass
        return is_active, files

    def has_next(self):
        is_active, files = self._get_queue_status()
        return is_active and len(files) > 0

    def clean(self, timeout=0):
        while self.has_next():
            self.dequeue()

    # Delete and clean are the same for local queue
    def delete(self):
        self.clean()
        with _local_queue_lock:
            os.remove(self.status_marker)

    def dequeue(self, acknowledge=True, timeout=0):
        wait_step = 1
        for waited in range(0, timeout + wait_step, wait_step):
            with _local_queue_lock:
                is_active, files = self._get_queue_status()
                if not is_active:
                    return None
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

            # self.logger.info(
            #    ('No messages found, sleeping for {} ' +
            #     ' (total sleep time {})').format(wait_step, waited))
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

    def shutdown(self, delete_queue=True):
        self.delete()

def get_local_queue_lock():
    return _local_queue_lock
