import unittest
import uuid
import os
import time
import logging


from studio.pubsub_queue import PubsubQueue
from studio.sqs_queue import SQSQueue

from studio.util import has_aws_credentials

logging.basicConfig()


class QueueTest(object):
    def get_queue(self):
        pass

    def test_simple(self):
        q = self.get_queue()
        q.clean()
        data = str(uuid.uuid4())

        q.enqueue(data)
        recv_data = q.dequeue(timeout=120)

        self.assertEquals(data, recv_data)
        self.assertTrue(q.dequeue() is None)

    def test_clean(self):
        q = self.get_queue()
        q.clean()
        data = str(uuid.uuid4())

        q.enqueue(data)
        q.clean(timeout=60)

        self.assertTrue(q.dequeue(timeout=60) is None)

    def test_enq_deq_order(self):
        return
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

        self.assertTrue(q.dequeue() is None)


class DistributedQueueTest(QueueTest):

    def test_unacknowledged(self):
        q = self.get_queue()
        q.clean()
        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        q.enqueue(data1)
        q.enqueue(data2)

        recv1 = q.dequeue(timeout=120)
        time.sleep(15)
        recv2 = q.dequeue(timeout=120)

        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertTrue(q.dequeue() is None)

    def test_two_receivers(self):
        logger = logging.getLogger('test_two_receivers')
        logger.setLevel(10)
        q1 = self.get_queue()
        q1.clean()

        q2 = self.get_queue(q1.get_name())

        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        logger.debug('data1 = ' + data1)
        logger.debug('data2 = ' + data2)

        q1.enqueue(data1)

        self.assertEquals(data1, q2.dequeue(timeout=120))

        q1.enqueue(data1)
        q1.enqueue(data2)

        recv1 = q1.dequeue(timeout=120)
        recv2 = q2.dequeue(timeout=120)

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

        msg = q.dequeue(timeout=120)
        self.assertEquals(data, msg)


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
