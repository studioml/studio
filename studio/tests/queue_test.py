import unittest
import uuid
import os
import time
from studio.pubsub_queue import PubsubQueue
from studio.local_queue import LocalQueue


class QueueTest(object):
    def get_queue(self):
        pass

    def test_simple(self):
        q = self.get_queue()
        q.clean()
        data = str(uuid.uuid4())

        q.enqueue(data)
        recv_data = q.dequeue()

        self.assertEquals(data, recv_data)
        self.assertFalse(q.has_next())

    def test_clean(self):
        q = self.get_queue()
        q.clean()
        data = str(uuid.uuid4())

        q.enqueue(data)
        q.clean()

        self.assertFalse(q.has_next())

    def test_enq_deq_order(self):
        q = self.get_queue()
        q.clean()
        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        q.enqueue(data1)
        time.sleep(1)
        q.enqueue(data2)

        recv_data1 = q.dequeue()
        recv_data2 = q.dequeue()

        self.assertEquals(data1, recv_data1)
        self.assertEquals(data2, recv_data2)

        self.assertFalse(q.has_next())


class LocalQueueTest(QueueTest, unittest.TestCase):
    def get_queue(self):
        return LocalQueue()


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in
    os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google ' +
    'PubSub')
class PubSubQueueTest(QueueTest, unittest.TestCase):
    def get_queue(self):
        return PubsubQueue('pubsub_queue_test')


if __name__ == '__main__':
    unittest.main()
