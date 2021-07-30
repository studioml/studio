import os
import uuid
import time
import filelock

from studio.artifacts.artifacts_tracker import get_studio_home
from studio.storage.storage_setup import get_storage_verbose_level
from studio.util import logs
from studio.util.util import check_for_kb_interrupt, rm_rf

LOCK_FILE_NAME = 'lock.lock'

class LocalQueue:
    def __init__(self, name: str, path: str = None, logger=None):
        if logger is not None:
            self._logger = logger
        else:
            self._logger = logs.get_logger('LocalQueue')
            self._logger.setLevel(get_storage_verbose_level())

        self.name = name
        if path is None:
            self.path = self._get_queue_directory()
        else:
            self.path = path
        self.path = os.path.join(self.path, name)
        os.makedirs(self.path, exist_ok=True)

        # Local queue is considered active, iff its directory exists.
        self._lock_path = os.path.join(self.path, LOCK_FILE_NAME)
        self._lock = filelock.SoftFileLock(self._lock_path)


    def _get_queue_status(self):
        is_active = os.path.isdir(self.path)
        if is_active:
            try:
                with self._lock:
                    files = os.listdir(self.path)
                    files.remove(LOCK_FILE_NAME)
                    return True, files
            except BaseException as exc:
                check_for_kb_interrupt()
                self._logger.info("FAILED to get queue status for %s - %s",
                                  self.path, exc)
                # Ignore possible exception:
                # we just want list of files without internal lock file
        return False, list()

    def _get_queue_directory(self):
        queue_dir: str = os.path.join(
            get_studio_home(),
            'queue')
        return queue_dir

    def has_next(self):
        is_active, files = self._get_queue_status()
        return is_active and len(files) > 0

    def is_active(self):
        is_active = os.path.isdir(self.path)
        return is_active

    def clean(self, timeout=0):
        _ = timeout
        rm_rf(self.path)

    def delete(self):
        self.clean()

    def _get_time(self, file: str):
        return os.path.getmtime(os.path.join(self.path, file))

    def dequeue(self, acknowledge=True, timeout=0):
        sleep_in_seconds = 1
        total_wait_time = 0
        if not self.is_active():
            return None

        while True:
            with self._lock:
                is_active, files = self._get_queue_status()
                if not is_active:
                    return None, None
                if any(files):
                    first_file = min([(p, self._get_time(p)) for p in files],
                                     key=lambda t: t[1])[0]
                    first_file = os.path.join(self.path, first_file)

                    with open(first_file, 'r') as f_in:
                        data = f_in.read()

                    if acknowledge:
                        self.acknowledge(first_file)
                        return data, None
                    return data, first_file

            if total_wait_time >= timeout:
                return None, None
            time.sleep(sleep_in_seconds)
            total_wait_time += sleep_in_seconds

    def enqueue(self, data):
        with self._lock:
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
        return self.name

    def get_path(self):
        return self.path

    def shutdown(self, delete_queue=True):
        _ = delete_queue
        self.delete()
