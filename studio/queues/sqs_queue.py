import boto3
import time
from typing import Dict

from studio.credentials.credentials import Credentials, KEY_CREDENTIALS
from studio.storage.storage_setup import get_storage_verbose_level
from studio.util import logs, util

class SQSQueue:

    def __init__(self, name,
                 config=None, logger=None):

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logs.getLogger('SQSQueue')
            self.logger.setLevel(get_storage_verbose_level())

        self.name = name
        self.region_name = None
        self.receive_timeout = None
        self.retry_time = None
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.aws_session_token = None
        self.profile_name = None
        self.is_persistent = False

        if config is not None:
            self._setup_from_config(config)

        if self.profile_name is not None:
            # If profile name is specified, for whatever reason
            # boto3 API will barf if (key, secret key) pair
            # is also defined.
            self.aws_access_key_id = None
            self.aws_secret_access_key = None

        self._session = boto3.session.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
            profile_name=self.profile_name
        )
        self._client = self._session.client('sqs')

        create_q_response = self._client.create_queue(
            QueueName=name)

        self.queue_url = create_q_response['QueueUrl']
        self.logger.info('Creating SQS queue with name %s', name)
        self.logger.info('Queue url = %s', self.queue_url)


    def _setup_from_config(self, config):
        queue_params = config.get('cloud', {})\
            .get('queue', {})\
            .get('sqs', {})
        self.is_persistent =\
            self._get_bool_flag(queue_params, 'persistent')
        cred_params = queue_params.get(KEY_CREDENTIALS, {})
        credentials = Credentials(cred_params)

        self.aws_access_key_id =\
            credentials.get_key()
        self.aws_secret_access_key =\
            credentials.get_secret_key()
        self.aws_session_token =\
            credentials.get_session_token()
        self.region_name =\
            credentials.get_region()
        self.profile_name =\
            credentials.get_profile()


    def _get_bool_flag(self, config: Dict, key: str) -> bool:
        value = config.get(key, False)
        if isinstance(value, str):
            value = value.lower() == 'true'
        return value

    def get_name(self):
        return self.name

    def clean(self, timeout=0):
        while True:
            msg = self.dequeue(timeout=timeout)
            if not msg:
                break

    def enqueue(self, msg):
        self.logger.debug("Sending message {} to queue with url {} "
                          .format(msg, self.queue_url))
        self._client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=msg)

    def has_next(self):
        raise NotImplementedError(
            'Using has_next with distributed queue ' +
            'such as pubsub will bite you in the ass! ' +
            'Use dequeue with timeout instead')

        no_tries = 3
        for _ in range(no_tries):
            response = self._client.receive_message(
                QueueUrl=self.queue_url)

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
                QueueUrl=self.queue_url)
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
        util.retry(lambda: self._client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=ack_id),
            sleep_time=10, logger=self.logger)

    def hold(self, ack_id, minutes):
        self._client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=ack_id,
            VisibilityTimeout=int(minutes * 60))

    def delete(self):
        self._client.delete_queue(QueueUrl=self.queue_url)

    def shutdown(self, delete_queue=True):
        self.delete()
