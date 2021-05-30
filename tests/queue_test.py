import unittest
import uuid
import os
import time
import yaml

from studio.pubsub_queue import PubsubQueue
from studio.queues.sqs_queue import SQSQueue
from studio.queues.local_queue import LocalQueue, get_local_queue_lock

from studio.extra_util import has_aws_credentials
from studio import model
from studio.util import logs

# Configuration of specific queue instance
# is driven primarily by queue name itself.
queue_name = "rmq_test_queue"

def _get_queue_name():
    global queue_name
    return queue_name

def _get_config():
    config_name = "test_config.yaml"
    config_file = os.path.join(
        os.path.dirname(
            os.path.realpath(__file__)),
        config_name)
    with open(config_file) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    return config

def _get_provider():
    config = _get_config()
    return model.get_db_provider(config)

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

    def get_queue_data(self, data):
        if data is None:
            return None
        data = data[0]
        if isinstance(data, str):
            return data
        if isinstance(data, bytes):
            return data.decode('utf-8')
        raise ValueError("unexpected type of queue data")

    def test_simple(self):
        with self.get_lock():
            q = self.get_queue()
            q.clean()
            data = str(uuid.uuid4())

            q.enqueue(data)
            recv_data = q.dequeue(timeout=self.get_timeout())

            self.assertEqual(data, self.get_queue_data(recv_data))
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

        recv1 = self.get_queue_data(q.dequeue(timeout=self.get_timeout()))
        time.sleep(15)
        recv2 = self.get_queue_data(q.dequeue(timeout=self.get_timeout()))

        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertTrue(q.dequeue() is None)

    def test_two_receivers(self):
        logger = logs.get_logger('test_two_receivers')
        logger.setLevel(10)
        q1 = self.get_queue()
        q1.clean()

        q2 = self.get_queue(q1.get_name())

        data1 = str(uuid.uuid4())
        data2 = str(uuid.uuid4())

        logger.debug('data1 = ' + data1)
        logger.debug('data2 = ' + data2)

        q1.enqueue(data1)
        recv_data1 = self.get_queue_data(
            q2.dequeue(timeout=self.get_timeout()))

        self.assertEqual(data1, recv_data1)

        q1.enqueue(data1)
        q1.enqueue(data2)

        recv_data1 = q1.dequeue(timeout=self.get_timeout())
        recv_data2 = q2.dequeue(timeout=self.get_timeout())

        recv1 = self.get_queue_data(recv_data1)
        recv2 = self.get_queue_data(recv_data2)

        logger.debug('recv1 = ' + recv1)
        logger.debug('recv2 = ' + recv2)

        self.assertTrue(data1 == recv1 or data2 == recv1)
        self.assertTrue(data1 == recv2 or data2 == recv2)
        self.assertFalse(recv1 == recv2)

        self.assertTrue(q1.dequeue() is None)
        self.assertTrue(q2.dequeue() is None)

    # Need to clarify if we need queue.hold() function at all.
    @unittest.skip
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
        return 20

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
     not _get_queue_name().startswith('sqs'),
    "Queue name specified is not SQSQueue")
class SQSQueueTest(DistributedQueueTest, unittest.TestCase):
    _multiprocess_shared_ = True

    def get_queue(self, name=None):
        return SQSQueue(
            'sqs_queue_test_' + str(uuid.uuid4()) if not name else name)

@unittest.skipIf(
     not _get_queue_name().startswith('rmq'),
    "Queue name specified is not RMQ Queue")
class RMQueueTest(DistributedQueueTest, unittest.TestCase):
    _multiprocess_shared_ = True

    def get_queue(self, name=None):
        config = _get_config()
        name = _get_queue_name()
        return model.get_queue(queue_name=name, config=config)

if __name__ == '__main__':
    unittest.main()
