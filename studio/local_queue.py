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

    def is_active(self):
        is_active = os.path.isfile(self.status_marker)
        return is_active

    def clean(self, timeout=0):
        with _local_queue_lock:
            _, files = self._get_queue_status()
            for f in files:
                try:
                    os.remove(f)
                except:
                    pass

    def delete(self):
        self.clean()
        with _local_queue_lock:
            try:
                os.remove(self.status_marker)
            except:
                    pass

    def dequeue(self, acknowledge=True, timeout=0):
        sleep_in_seconds = 1
        total_wait_time = 0
        while True:
            with _local_queue_lock:
                is_active, files = self._get_queue_status()
                if not is_active:
                    return None
                if any(files):
                    first_file = min([(p, os.path.getmtime(p)) for p in files],
                                     key=lambda t: t[1])[0]

                    with open(first_file, 'r') as f:
                        data = f.read()

                    if acknowledge:
                        self.acknowledge(first_file)
                        return data, None
                    else:
                        return data, first_file

            if total_wait_time >= timeout:
                return None
            # self.logger.info(
            #    ('No messages found, sleeping for {0} sec'
            #      .format(sleep_in_seconds))
            time.sleep(sleep_in_seconds)
            total_wait_time += sleep_in_seconds

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
