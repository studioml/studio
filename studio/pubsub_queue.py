from google.cloud import pubsub
import logging
import os
import time
logging.basicConfig()


class PubsubQueue(object):
    def __init__(self, queue_name, sub_name=None, verbose=10):
        assert 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys()
        self.client = pubsub.Client()
        self.topic = self.client.topic(queue_name)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)
        sub_name = sub_name if sub_name else queue_name + "_sub"
        self.logger.info("Topic name = {}".format(queue_name))
        self.logger.info("Subscription name = {}".format(sub_name))
        if queue_name not in [t.name for t in self.client.list_topics()]:
            self.topic.create()
            self.logger.info('topic {} created'.format(queue_name))

        self.subscription = self.topic.subscription(sub_name)
        if sub_name not in [s.name for s in self.topic.list_subscriptions()]:
            self.subscription.create()
            self.logger.info('subscription {} created'.format(sub_name))

        self.messages = []
        self.ack_timeout = 10

    def clean(self):
        while self.has_next():
            self.dequeue()

    def get_name(self):
        return self.topic.name

    def _filter_stale_messages(self):
        self.messages = [
            m for m in self.messages if (
                time.time() -
                m[2]) < self.ack_timeout]

    def has_next(self):
        self._filter_stale_messages()
        if not any(self.messages):
            pulled_messages = self.subscription.pull(
                return_immediately=True, max_messages=1)
            self.messages += [(m[0], m[1], time.time()) for m in
                              pulled_messages]

        return any(self.messages)

    def enqueue(self, data):
        data = data.encode('utf-8')
        msg_id = self.topic.publish(data)
        self.logger.debug('Message with id {} published'.format(msg_id))

    def dequeue(self, acknowledge=True):
        if not self.has_next():
            return None

        retval = self.messages[0]
        self.messages = self.messages[1:]
        if acknowledge:
            self.acknowledge(retval[0])
            self.logger.debug("Message {} received and acknowledged"
                              .format(retval[1].message_id))

            return retval[1].data
        else:
            self.logger.debug("Message {} received, ack_id {}"
                              .format(retval[1].message_id, retval[0]))
            return (retval[1].data, retval[0])

    def acknowledge(self, ack_key):
        self.logger.debug("Message with key {} acknowledged".format(ack_key))
        self.subscription.acknowledge([ack_key])
