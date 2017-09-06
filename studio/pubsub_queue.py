from google.cloud import pubsub
import logging
import os
import json

from model import parse_verbosity

logging.basicConfig()


class PubsubQueue(object):
    def __init__(self, queue_name, sub_name=None, verbose=10):
        assert 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys()
        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS']) as f:
            credentials = json.loads(f.read())

        project_name = credentials['project_id']
        self.logger = logging.getLogger(self.__class__.__name__)
        if verbose is not None:
            self.logger.setLevel(parse_verbosity(verbose))

        self.pubclient = pubsub.PublisherClient()
        self.subclient = pubsub.SubscriberClient()

        self.project = project_name
        self.topic_name = self.pubclient.topic_path(project_name, queue_name)
        self.logger.info("Topic name = {}".format(self.topic_name))
        try:
            self.pubtopic = self.pubclient.get_topic(self.topic_name)
        except BaseException as e:
            self.pubtopic = self.pubclient.create_topic(self.topic_name)
            self.logger.info('topic {} created'.format(self.topic_name))

        sub_name = sub_name if sub_name else queue_name + "_sub"
        self.logger.info("Topic name = {}".format(queue_name))
        self.logger.info("Subscription name = {}".format(sub_name))

        self.sub_name = self.subclient.subscription_path(
            project_name, sub_name)
        try:
            self.subclient.get_subscription(self.sub_name)
        except BaseException as e:
            self.logger.warn(e)
            self.subclient.create_subscription(self.sub_name, self.topic_name)

        self.logger.info('subscription {} created'.format(sub_name))

    def clean(self):
        while self.has_next():
            self.dequeue()

    def get_name(self):
        return self.subclient.match_topic_from_topic_name(self.topic_name)

    def has_next(self):
        response = self.subclient.api.pull(
            self.sub_name,
            return_immediately=True, max_messages=1)
        messages = response.received_messages
        retval = any(messages)

        for m in messages:
            self.hold(m.ack_id, 0)

        return retval

    def enqueue(self, data):
        data = data.encode('utf-8')
        msg_id = self.pubclient.publish(self.topic_name, data)
        self.logger.debug('Message with id {} published'.format(msg_id))

    def dequeue(self, acknowledge=True):

        response = self.subclient.api.pull(
            self.sub_name,
            return_immediately=True, max_messages=1)
        msgs = response.received_messages

        if not any(msgs):
            return None

        retval = msgs[0]

        if acknowledge:
            self.acknowledge(retval.ack_id)
            self.logger.debug("Message {} received and acknowledged"
                              .format(retval.message.message_id))

            return retval.message.data
        else:
            self.logger.debug(
                "Message {} received, ack_id {}" .format(
                    retval.message.message_id,
                    retval.ack_id))
            return (retval.message.data, retval.ack_id)

    def hold(self, ack_key, delay=5):
        self.logger.debug(
            ("Message acknoledgment deadline is extended by {} " +
             "min for {}").format(
                delay,
                ack_key))
        self.subclient.modify_ack_deadline(
            self.sub_name, [ack_key], int(delay * 60))

    def acknowledge(self, ack_key):
        self.logger.debug("Message with key {} acknowledged".format(ack_key))
        self.subclient.acknowledge(self.sub_name, [ack_key])
