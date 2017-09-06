import logging
import time

try:
    import boto3
except BaseException:
    boto3 = None

from model import parse_verbosity

logging.basicConfig()


class SQSQueue(object):

    def __init__(self, name, verbose=10, receive_timeout=300,
                 retry_time=10, region_name='us-east-1'):
        assert boto3 is not None
        self._client = boto3.client('sqs', region_name=region_name)

        create_q_response = self._client.create_queue(
            QueueName=name)

        self._queue_url = create_q_response['QueueUrl']
        self.logger = logging.getLogger('SQSQueue')
        if verbose is not None:
            self.logger.setLevel(parse_verbosity(verbose))
        self._name = name
        self.logger.info('Creating SQS queue with name ' + name)
        self.logger.info('Queue url = ' + self._queue_url)

        self._receive_timeout = receive_timeout
        self._retry_time = retry_time

    def get_name(self):
        return self._name

    def clean(self):
        while self.has_next():
            self.dequeue()

    def enqueue(self, msg):
        self.logger.debug("Sending message {} to queue with url {} "
                          .format(msg, self._queue_url))
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=msg)

    def has_next(self):
        response = self._client.receive_message(
            QueueUrl=self._queue_url)

        if 'Messages' not in response.keys():
            return False

        msgs = response['Messages']

        for m in msgs:
            self.logger.debug('Received message {} '.format(m['MessageId']))
            self.hold(m['ReceiptHandle'], 0)

        return any(msgs)

    def dequeue(self, acknowledge=True):
        counter = 0
        response = self._client.receive_message(
            QueueUrl=self._queue_url)
        while 'Messages' not in response.keys() \
                and counter < self._receive_timeout:
            self.logger.debug(
                ('No messages received, sleeping and retrying ' +
                 '({} attempts left)...') .format(
                    (self._receive_timeout -
                     counter) //
                    self._retry_time))
            time.sleep(self._retry_time)
            response = self._client.receive_message(
                QueueUrl=self._queue_url)
            counter += self._retry_time

        if 'Messages' not in response.keys():
            return None

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
        self._client.delete_message(
            QueueUrl=self._queue_url,
            ReceiptHandle=ack_id)

    def hold(self, ack_id, minutes):
        self._client.change_message_visibility(
            QueueUrl=self._queue_url,
            ReceiptHandle=ack_id,
            VisibilityTimeout=int(minutes * 60))
