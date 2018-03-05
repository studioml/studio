import time

try:
    import boto3
except BaseException:
    boto3 = None

from .model import parse_verbosity
from .util import retry
from . import logs


class SQSQueue(object):

    def __init__(self, name, verbose=10, receive_timeout=300,
                 retry_time=10):
        assert boto3 is not None
        self._client = boto3.client('sqs')

        create_q_response = self._client.create_queue(
            QueueName=name)

        self._queue_url = create_q_response['QueueUrl']
        self.logger = logs.getLogger('SQSQueue')
        if verbose is not None:
            self.logger.setLevel(parse_verbosity(verbose))
        self._name = name
        self.logger.info('Creating SQS queue with name ' + name)
        self.logger.info('Queue url = ' + self._queue_url)

        self._receive_timeout = receive_timeout
        self._retry_time = retry_time

    def get_name(self):
        return self._name

    def clean(self, timeout=0):
        while True:
            msg = self.dequeue(timeout=timeout)
            if not msg:
                break

    def enqueue(self, msg):
        self.logger.debug("Sending message {} to queue with url {} "
                          .format(msg, self._queue_url))
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=msg)

    def has_next(self):
        raise NotImplementedError(
            'Using has_next with distributed queue ' +
            'such as pubsub will bite you in the ass! ' +
            'Use dequeue with timeout instead')

        no_tries = 3
        for _ in range(no_tries):
            response = self._client.receive_message(
                QueueUrl=self._queue_url)

            if 'Messages' not in response.keys():
                time.sleep(5)
                continue
            else:
                break

        msgs = response.get('Messages', [])

        for m in msgs:
            self.logger.debug('Received message {} '.format(m['MessageId']))
            self.hold(m['ReceiptHandle'], 0)

        return any(msgs)

    def dequeue(self, acknowledge=True, timeout=0):
        wait_step = 1
        for waited in range(0, timeout + wait_step, wait_step):
            response = self._client.receive_message(
                QueueUrl=self._queue_url)
            msgs = response.get('Messages', [])
            if any(msgs):
                break
            elif waited == timeout:
                return None
            else:
                self.logger.info(
                    ('No messages found, sleeping for {} ' +
                     ' (total sleep time {})').format(wait_step, waited))
                time.sleep(wait_step)

        msgs = response['Messages']

        if not any(msgs):
            return None

        retval = msgs[0]

        if acknowledge:
            self.acknowledge(retval['ReceiptHandle'])
            self.logger.debug("Message {} received and acknowledged"
                              .format(retval['MessageId']))

            return retval['Body']
        else:
            self.logger.debug("Message {} received, ack_id {}"
                              .format(retval['MessageId'],
                                      retval['ReceiptHandle']))
            return (retval['Body'], retval['ReceiptHandle'])

    def acknowledge(self, ack_id):
        retry(lambda: self._client.delete_message(
            QueueUrl=self._queue_url,
            ReceiptHandle=ack_id),

            sleep_time=10, logger=self.logger)

    def hold(self, ack_id, minutes):
        self._client.change_message_visibility(
            QueueUrl=self._queue_url,
            ReceiptHandle=ack_id,
            VisibilityTimeout=int(minutes * 60))

    def delete(self):
        self._client.delete_queue(QueueUrl=self._queue_url)
