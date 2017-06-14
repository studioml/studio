from google.cloud import pubsub
import logging
from google.gax.errors import RetryError
import os
logging.basicConfig()


class PubsubQueue(object):
    def __init__(self, queue_name, sub_name=None):
        assert 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys()
        print(dir(pubsub))
        self.client = pubsub.Client()
        self.topic = self.client.topic(queue_name)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(10)
        sub_name = sub_name if sub_name else queue_name + "_sub"
        self.logger.info("Topic name = {}".format(queue_name))
        self.logger.info("Subscription name = {}".format(queue_name))
        if queue_name not in [t.name for t in self.client.list_topics()]:
            self.topic.create()
            self.logger.info('topic {} created'.format(queue_name))

        self.subscription = self.topic.subscription(sub_name)
        if sub_name not in [s.name for s in self.topic.list_subscriptions()]:
            self.subscription.create()
            self.logger.info('subscription {} created'.format(sub_name))

        self.messages = []

    def clean(self):
        while self.has_next():
            self.dequeue()

    def get_name(self):
        return self.topic.name

    def has_next(self):
        self.messages += self.subscription.pull(
            return_immediately=True, max_messages=1)

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
            success = False
            while not success:
                try:
                    self.acknowledge(retval[0])
                    success = True
                except RetryError:
                    # remove messages with stale ack_id
                    success = False
                    if not any(self.messages):
                        raise ValueError('All received messages are stale')

                    retval = self.messages[0]
                    self.messages = self.messages[1:]

            return retval[1].data
        else:
            return (retval[1].data, retval[0])

    def acknowledge(self, ack_key):
        self.subscription.acknowledge([ack_key])
