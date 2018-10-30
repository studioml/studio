import hashlib
import six
from studio import util


def clientFunction(args, files):
    print('client function call with args ' +
          str(args) + ' and files ' + str(files))

    cs_files = {'output', 'clientscript', 'args'}
    filehashes = {
        k: util.filehash(
            v,
            hashobj=hashlib.md5()) for k,
        v in six.iteritems(files) if k not in cs_files}

    return (args, filehashes)
