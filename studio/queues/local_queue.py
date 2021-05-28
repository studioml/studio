import os
import sys
import uuid
import glob
import time
import filelock

from studio.artifacts.artifacts_tracker import get_studio_home
from studio.util import logs
from studio.util.util import check_for_kb_interrupt

_local_queue_lock = filelock.FileLock(
    os.path.expanduser('~/.studioml/local_queue.lock')
)

class LocalQueue:
    def __init__(self, path=None, verbose=10):
        if path is None:
            self.path = self._get_queue_directory()
        else:
            self.path = path
        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(verbose)
        self.status_marker = os.path.join(self.path, 'is_active.queue')
        try:
            with open(self.status_marker, "w") as smark:
                _ = smark
        except IOError:
            self.logger.error('FAILED to create %s for LocalQueue. ABORTING.',
                              self.status_marker)
            sys.exit(-1)

    def _get_queue_status(self):
        with _local_queue_lock:
            files = glob.glob(self.path + '/*')
            if files is None:
                files = list()
        is_active = self.status_marker in files
        try:
            files.remove(self.status_marker)
        except BaseException:
            check_for_kb_interrupt()
            # Ignore possible exception:
            # we just want list of files without status marker

        return is_active, files

    def _get_queue_directory(self):
        queue_dir = os.path.join(
            get_studio_home(),
            'queue')
        if not os.path.exists(queue_dir):
            try:
                os.makedirs(queue_dir)
            except OSError:
                pass

        return queue_dir

    def has_next(self):
        is_active, files = self._get_queue_status()
        return is_active and len(files) > 0

    def is_active(self):
        is_active = os.path.isfile(self.status_marker)
        return is_active

    def clean(self, timeout=0):
        _ = timeout
        with _local_queue_lock:
            _, files = self._get_queue_status()
            for one_file in files:
                try:
                    os.remove(one_file)
                except BaseException:
                    check_for_kb_interrupt()


    def delete(self):
        self.clean()
        with _local_queue_lock:
            try:
                os.remove(self.status_marker)
            except BaseException:
                check_for_kb_interrupt()


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

                    with open(first_file, 'r') as f_in:
                        data = f_in.read()

                    if acknowledge:
                        self.acknowledge(first_file)
                        return data, None
                    return data, first_file

            if total_wait_time >= timeout:
                return None
            time.sleep(sleep_in_seconds)
            total_wait_time += sleep_in_seconds

    def enqueue(self, data):
        with _local_queue_lock:
            filename = os.path.join(self.path, str(uuid.uuid4()))
            with open(filename, 'w') as f_out:
                f_out.write(data)

    def acknowledge(self, key):
        try:
            os.remove(key)
        except BaseException:
            check_for_kb_interrupt()

    def hold(self, key, minutes):
        _ = minutes
        self.acknowledge(key)

    def get_name(self):
        return 'local'

    def get_path(self):
        return self.path

    def shutdown(self, delete_queue=True):
        _ = delete_queue
        self.delete()

def get_local_queue_lock():
    return _local_queue_lock
