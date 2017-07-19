import os
import fs_tracker
import uuid
import glob


class LocalQueue:
    def __init__(self, path=None):
        if path is None:
            self.path = fs_tracker.get_queue_directory()
        else:
            self.path = path

    def has_next(self):
        return any(glob.glob(self.path + '/*'))

    def clean(self):
        while self.has_next():
            self.dequeue()

    def dequeue(self, acknowledge=True):
        files = glob.glob(self.path + '/*')
        if not any(files):
            return None

        first_file = min([(p, os.path.getmtime(p)) for p in files],
                         key=lambda t: t[1])[0]

        with open(first_file, 'r') as f:
            data = f.read()

        if not acknowledge:
            return data, first_file
        else:
            self.acknowledge(first_file)
            return data

    def enqueue(self, data):
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
        return self.path
