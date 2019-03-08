import unittest
import uuid
import os
import time

from studio.pubsub_queue import PubsubQueue
from studio.sqs_queue import SQSQueue
from studio.local_queue import LocalQueue, get_local_queue_lock

from studio.util import has_aws_credentials
from studio import logs


class DummyContextManager(object):
    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class QueueTest(object):
    def get_queue(self):
        pass

    def test_simple(self):
        with self.get_lock():
            q = self.get_queue()
            q.clean()
            data = str(uuid.uuid4())

            q.enqueue(data)
            recv_data = q.dequeue(timeout=self.get_timeout())

            self.assertEquals(data, recv_data)
            self.assertTrue(q.dequeue() is None)

    def test_clean(self):
        with self.get_lock():
            q = self.get_queue()
            q.clean()
            data = str(uuid.uuid4())

            q.enqueue(data)
            q.clean(timeout=self.get_timeout())

            self.assertTrue(q.dequeue(timeout=self.get_timeout()) is None)

    def get_lock(self):
        return DummyContextManager()

    def get_timeout(self):
        return 0


class LocalQueueTest(QueueTest, unittest.TestCase):
    def get_queue(self):
        return LocalQueue()

    def get_lock(self):
        return get_local_queue_lock()


class DistributedQueueTest(QueueTest):

    def test_unacknowledged(self):
        q = self.get_queue()
        q.clean()
        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        q.enqueue(data1)
        q.enqueue(data2)

        recv1 = q.dequeue(timeout=self.get_timeout())
        time.sleep(15)
        recv2 = q.dequeue(timeout=self.get_timeout())

        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertTrue(q.dequeue() is None)

    def test_two_receivers(self):
        logger = logs.getLogger('test_two_receivers')
        logger.setLevel(10)
        q1 = self.get_queue()
        q1.clean()

        q2 = self.get_queue(q1.get_name())

        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        logger.debug('data1 = ' + data1)
        logger.debug('data2 = ' + data2)

        q1.enqueue(data1)

        self.assertEquals(data1, q2.dequeue(timeout=self.get_timeout()))

        q1.enqueue(data1)
        q1.enqueue(data2)

        recv1 = q1.dequeue(timeout=self.get_timeout())
        recv2 = q2.dequeue(timeout=self.get_timeout())

        logger.debug('recv1 = ' + recv1)
        logger.debug('recv2 = ' + recv2)

        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertTrue(q1.dequeue() is None)
        self.assertTrue(q2.dequeue() is None)

    def test_hold(self):
        q = self.get_queue()
        q.clean()

        data = str(uuid.uuid4())
        q.enqueue(data)

        msg, ack_id = q.dequeue(acknowledge=False, timeout=60)
        q.hold(ack_id, 1.5)

        self.assertTrue(q.dequeue(timeout=10) is None)

        msg = q.dequeue(timeout=self.get_timeout())
        self.assertEquals(data, msg)

    def get_timeout(self):
        return 120


@unittest.skipIf(
    'GOOGLE_APPLICATION_CREDENTIALS' not in
    os.environ.keys(),
    'GOOGLE_APPLICATION_CREDENTIALS environment ' +
    'variable not set, won'' be able to use google ' +
    'PubSub')
class PubSubQueueTest(DistributedQueueTest, unittest.TestCase):
    _multiprocess_shared_ = True

    def get_queue(self, name=None):
        name = 'pubsub_queue_test' + str(uuid.uuid4()) if not name else name
        print(name)
        return PubsubQueue(name)


@unittest.skipIf(
    not has_aws_credentials(),
    "AWS credentials is not present, cannot use SQSQueue")
class SQSQueueTest(DistributedQueueTest, unittest.TestCase):
    _multiprocess_shared_ = True

    def get_queue(self, name=None):
        return SQSQueue(
            'sqs_queue_test_' + str(uuid.uuid4()) if not name else name)


if __name__ == '__main__':
    unittest.main()
