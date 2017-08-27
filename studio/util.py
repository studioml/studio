import hashlib
import StringIO
import re
import binascii
import random

def remove_backspaces(line):
    splitline = re.split('(\x08+)', line)
    buf = StringIO.StringIO()
    for i in range(0, len(splitline) - 1, 2):
        buf.write(splitline[i][:-len(splitline[i + 1])])

    if len(splitline) % 2 == 1:
        buf.write(splitline[-1])

    return buf.getvalue()


def sha256_checksum(filename, block_size=65536):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()

def randstring(length):
    return "".join([random.choice(string.ascii_letters + string.digits) \
        for n in xrange(30)])
