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
        # neither pubsub nor local queue are actually 
        # very punctual about the order. This delay is 
        # intended to ensure the messages are not 
        # swapped accidentally
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
    _multiprocess_can_split_ = True

    def get_queue(self):
        return PubsubQueue('pubsub_queue_test_' + str(uuid.uuid4()))

    def test_unacknowledged(self):
        q = self.get_queue()
        q.clean()
        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        q.enqueue(data1)
        self.assertTrue(q.has_next())
        self.assertTrue(q.has_next())
        q.enqueue(data2)

        self.assertTrue(q.has_next())
        recv_data1 = q.dequeue()
        self.assertTrue(q.has_next())
        time.sleep(15)

        self.assertTrue(q.has_next())
        recv_data2 = q.dequeue()

        self.assertEquals(data1, recv_data1)
        self.assertEquals(data2, recv_data2)
        self.assertFalse(q.has_next())

    def test_two_receivers(self):
        q1 = self.get_queue()
        q1.clean()

        q2 = PubsubQueue(q1.get_name())

        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        q1.enqueue(data1)

        self.assertEquals(data1, q2.dequeue())

        q1.enqueue(data1)
        q1.enqueue(data2)

        recv1 = q1.dequeue()
        recv2 = q2.dequeue()
        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertFalse(q1.has_next())
        self.assertFalse(q2.has_next())


if __name__ == '__main__':
    unittest.main()
