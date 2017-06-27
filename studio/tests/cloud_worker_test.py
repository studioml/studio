import unittest

from studio.cloud_worker import GCloudWorkerManager

class CloudWorkerManagerTest(object):
    def get_worker_manager(self):
        pass

    def test_start_stop(self):
        wm = self.get_worker_manager()
        queue_name = 'test_gcloud'
        worker_id = wm.start_worker(queue_name)
        wm.stop_worker(worker_id)


class GoogleCloudWorkerManagerTest(CloudWorkerManagerTest, unittest.TestCase):
    def get_worker_manager(self):
        project = 'studio-ed756'
        return GCloudWorkerManager(project)



if __name__ == '__main__':
    unittest.main()
