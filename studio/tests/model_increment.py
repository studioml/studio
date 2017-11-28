import six


def create_model(modeldir):

    def model(data):
        retval = {}
        for k, v in six.iteritems(data):
            retval[k] = v + 1
        return retval

    return model
