from google.cloud import pubsub
import logging
import os
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

    def clean(self):
        while self.has_next():
            self.dequeue()

    def get_name(self):
        return self.topic.name

    def has_next(self):
        messages = self.subscription.pull(
            return_immediately=True, max_messages=1)
        retval = any(messages)

        for m in messages:
            self.hold(m[0], 0)

        return retval

    def enqueue(self, data):
        data = data.encode('utf-8')
        msg_id = self.topic.publish(data)
        self.logger.debug('Message with id {} published'.format(msg_id))

    def dequeue(self, acknowledge=True):

        msgs = self.subscription.pull(return_immediately=True, max_messages=1)
        if not any(msgs):
            return None

        retval = msgs[0]

        if acknowledge:
            self.acknowledge(retval[0])
            self.logger.debug("Message {} received and acknowledged"
                              .format(retval[1].message_id))

            return retval[1].data
        else:
            self.logger.debug("Message {} received, ack_id {}"
                              .format(retval[1].message_id, retval[0]))
            return (retval[1].data, retval[0])

    def hold(self, ack_key, delay=5):
        self.logger.debug(
            ("Message acknoledgment deadline is extended by {} " +
             "min for {}").format(
                delay,
                ack_key))
        self.subscription.modify_ack_deadline([ack_key], int(delay * 60))

    def acknowledge(self, ack_key):
        self.logger.debug("Message with key {} acknowledged".format(ack_key))
        self.subscription.acknowledge([ack_key])
