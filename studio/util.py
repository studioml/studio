import hashlib
from io import StringIO
from datetime import timedelta
import re
import random
import string
import struct
import time
import sys
import shutil
import subprocess
import os
import threading
import numpy as np
import requests
import six
from botocore.exceptions import ClientError
from pygtail import Pygtail
from . import model_setup
from .base_artifact_store import BaseArtifactStore

DAY = 86400
HOUR = 3600
MINUTE = 60

def remove_backspaces(line):
    splitline = re.split('(\x08+)', line)
    try:
        splitline = [unicode(s, 'utf-8') for s in splitline]
    except NameError:
        splitline = [str(s) for s in splitline]

    buf = StringIO()
    for i in range(0, len(splitline) - 1, 2):
        buf.write(splitline[i][:-len(splitline[i + 1])])

    if len(splitline) % 2 == 1:
        buf.write(splitline[-1])

    return buf.getvalue()


def sha256_checksum(filename, block_size=65536):
    return filehash(filename, block_size, hashobj=hashlib.sha256())


def filehash(filename, block_size=65536, hashobj=hashlib.sha256()):
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            hashobj.update(block)
    return hashobj.hexdigest()


def rand_string(length):
    return "".join([random.choice(string.ascii_letters + string.digits)
                    for n in range(length)])


def event_reader(fileobj):
    from tensorflow.core.util import event_pb2

    if isinstance(fileobj, str):
        fileobj = open(fileobj, 'rb')

    header_len = 12
    footer_len = 4
    size_len = 8

    while True:
        try:
            data_len = struct.unpack('Q', fileobj.read(size_len))[0]
            fileobj.read(header_len - size_len)

            data = fileobj.read(data_len)

            event = None
            event = event_pb2.Event()
            event.ParseFromString(data)

            fileobj.read(footer_len)
            yield event
        except BaseException:
            break

    fileobj.close()


def rsync_cp(source, dest, ignore_arg='', logger=None):
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest) if os.path.isdir(dest) else os.remove(dest)
        os.makedirs(dest)
    except OSError:
        pass

    if ignore_arg != '':
        source += "/"
        tool = 'rsync'
        args = [tool, ignore_arg, '-aHAXE', source, dest]
    else:
        try:
            os.rmdir(dest)
        except OSError:
            pass

        tool = 'cp'
        args = [
            tool,
            '-pR',
            source,
            dest
        ]

    pcp = subprocess.Popen(args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
    cpout, _ = pcp.communicate()
    if pcp.returncode != 0 and logger is not None:
        logger.info('%s returned non-zero exit code. Output:' % tool)
        logger.info(cpout)


class Progbar(object):
    """Displays a progress bar.

    # Arguments
        target: Total number of steps expected, None if unknown.
        interval: Minimum visual progress update interval (in seconds).
    """

    def __init__(self, target, width=30, verbose=1, interval=0.05):
        self.width = width
        if target is None:
            target = -1
        self.target = target
        self.sum_values = {}
        self.unique_values = []
        self.start = time.time()
        self.last_update = 0
        self.interval = interval
        self.total_width = 0
        self.seen_so_far = 0
        self.verbose = verbose

    def update(self, current, values=None, force=False):
        """Updates the progress bar.

        # Arguments
            current: Index of current step.
            values: List of tuples (name, value_for_last_step).
                The progress bar will display averages for these values.
            force: Whether to force visual progress update.
        """
        values = values or []
        for k, v in values:
            if k not in self.sum_values:
                self.sum_values[k] = [v * (current - self.seen_so_far),
                                      current - self.seen_so_far]
                self.unique_values.append(k)
            else:
                self.sum_values[k][0] += v * (current - self.seen_so_far)
                self.sum_values[k][1] += (current - self.seen_so_far)
        self.seen_so_far = current

        now = time.time()
        if self.verbose == 1:
            if not force and (now - self.last_update) < self.interval:
                return

            prev_total_width = self.total_width
            sys.stdout.write('\b' * prev_total_width)
            sys.stdout.write('\r')

            if self.target != -1:
                numdigits = int(np.floor(np.log10(self.target))) + 1
                barstr = '%%%dd/%%%dd [' % (numdigits, numdigits)
                bar = barstr % (current, self.target)
                prog = float(current) / self.target
                prog_width = int(self.width * prog)
                if prog_width > 0:
                    bar += ('=' * (prog_width - 1))
                    if current < self.target:
                        bar += '>'
                    else:
                        bar += '='
                bar += ('.' * (self.width - prog_width))
                bar += ']'
                sys.stdout.write(bar)
                self.total_width = len(bar)

            if current:
                time_per_unit = (now - self.start) / current
            else:
                time_per_unit = 0
            eta = time_per_unit * (self.target - current)
            info = ''
            if current < self.target and self.target != -1:
                info += ' - ETA: %ds' % eta
            else:
                info += ' - %ds' % (now - self.start)
            for k in self.unique_values:
                info += ' - %s:' % k
                if isinstance(self.sum_values[k], list):
                    avg = np.mean(
                        self.sum_values[k][0] / max(1, self.sum_values[k][1]))
                    if abs(avg) > 1e-3:
                        info += ' %.4f' % avg
                    else:
                        info += ' %.4e' % avg
                else:
                    info += ' %s' % self.sum_values[k]

            self.total_width += len(info)
            if prev_total_width > self.total_width:
                info += ((prev_total_width - self.total_width) * ' ')

            sys.stdout.write(info)
            sys.stdout.flush()

            if current >= self.target:
                sys.stdout.write('\n')

        if self.verbose == 2:
            if current >= self.target:
                info = '%ds' % (now - self.start)
                for k in self.unique_values:
                    info += ' - %s:' % k
                    avg = np.mean(
                        self.sum_values[k][0] / max(1, self.sum_values[k][1]))
                    if avg > 1e-3:
                        info += ' %.4f' % avg
                    else:
                        info += ' %.4e' % avg
                sys.stdout.write(info + "\n")

        self.last_update = now

    def add(self, n, values=None):
        self.update(self.seen_so_far + n, values)


def download_file(url, local_path, logger=None):
    if url.startswith('s3://') or url.startswith('gs://'):
        return download_file_from_qualified(url, local_path, logger)

    response = requests.get(
        url,
        stream=True)
    if logger:
        logger.info(("Trying to download file at url {} to " +
                     "local path {}").format(url, local_path))

    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            for chunk in response:
                f.write(chunk)
    elif logger:
        logger.info("Response error with code {}"
                    .format(response.status_code))

    return response


def upload_file(url, local_path, logger=None):
    if logger:
        logger.info(("Trying to upload file {} to " +
                     "url {}").format(local_path, url))
    tic = time.time()
    with open(local_path, 'rb') as f:
        resp = requests.put(url, data=f)

    if resp.status_code != 200 and logger:
        logger.error(str(resp.reason))

    if logger:
        logger.debug('File upload done in {} s'
                     .format(time.time() - tic))

def _looks_like_url(name):
    """
    Function tries to determine if input argument
    looks like URL and not like S3 bucket name.
    :param name - input name
    :return: True, if name looks like URL;
             False otherwise.
    """
    if name.endswith('.com'):
        return True
    if name.find(':') >= 0:
        # Assume it is port number
        return True
    return False

def download_file_from_qualified(qualified, local_path, logger=None):
    if qualified.startswith('dockerhub://') or \
       qualified.startswith('shub://'):
        return

    assert qualified.startswith('s3://') or \
        qualified.startswith('gs://')

    qualified_split = qualified.split('/')
    if _looks_like_url(qualified_split[2]):
        bucket = qualified_split[3]
        key = '/'.join(qualified_split[4:])
    else:
        bucket = qualified_split[2]
        key = '/'.join(qualified_split[3:])

    if logger is not None:
        logger.debug(('Downloading file from bucket {} ' +
                      ' and key {} to local path {}')
                     .format(bucket, key, local_path))

    if qualified.startswith('s3://'):

        if qualified.endswith('/'):
            _s3_download_dir(bucket, key, local_path, logger=logger)
        else:
            s3_client = _get_active_s3_client()
            s3_client.download_file(bucket, key, local_path)
    else:
        raise NotImplementedError

def _get_active_s3_client():
    artifact_store = model_setup.get_model_artifact_store()
    if artifact_store is None \
        or not isinstance(artifact_store, BaseArtifactStore):
        raise NotImplementedError("Artifact store is not set up or has the wrong type")

    storage_client = artifact_store.get_storage_client()
    if storage_client is None:
        raise NotImplementedError("Expected boto3 storage client for current artifact store")
    return storage_client

def _s3_download_dir(bucket, dist, local, logger=None):
    s3_client = _get_active_s3_client()

    paginator = s3_client.get_paginator('list_objects')
    for result in paginator.paginate(
            Bucket=bucket,
            Delimiter='/',
            Prefix=dist):
        if result.get('CommonPrefixes') is not None:
            for subdir in result.get('CommonPrefixes'):
                _s3_download_dir(
                    bucket,
                    subdir.get('Prefix'),
                    os.path.join(local, subdir.get('Prefix'))
                )

        if result.get('Contents') is not None:
            for file in result.get('Contents'):
                if not os.path.exists(
                    os.path.dirname(
                        local +
                        os.sep +
                        file.get('Key'))):
                    os.makedirs(
                        os.path.dirname(
                            local +
                            os.sep +
                            file.get('Key')))

                try:
                    key = file.get('Key')
                    local_path = os.path.join(
                        local,
                        re.sub('^' + dist, '', file.get('Key'))
                    )

                    if logger:
                        logger.debug(
                            'Downloading {}/{} to {}'
                            .format(bucket, key, local_path))

                    s3_client.download_file(bucket, key, local_path)
                except ClientError as e:
                    if logger:
                        logger.debug(
                            'Download failed with exception {}'.format(e))


def has_aws_credentials():
    s3_client = _get_active_s3_client()
    return s3_client._request_signer._credentials is not None

def retry(f,
          no_retries=5, sleep_time=1,
          exception_class=BaseException, logger=None):
    for i in range(no_retries):
        try:
            return f()
        except exception_class as e:
            if i == no_retries - 1:
                raise e

            if logger:
                logger.info(
                    ('Exception {} is caught, ' +
                     'sleeping {}s and retrying (attempt {} of {})')
                    .format(e, sleep_time, i, no_retries))
            time.sleep(sleep_time)


def compression_to_extension(compression):
    return _compression_to_extension_taropt(compression)[0]


def compression_to_taropt(compression):
    return _compression_to_extension_taropt(compression)[1]


def _compression_to_extension_taropt(compression):
    default_compression = 'none'
    if compression is None:
        compression = default_compression

    compression = compression.lower()

    if compression == 'bzip2':
        return '.bz2', '--bzip2'

    elif compression == 'gzip':
        return '.gz', '--gzip'

    elif compression == 'xz':
        return '.xz', '--xz'

    elif compression == 'lzma':
        return '.lzma', '--lzma'

    elif compression == 'lzop':
        return '.lzop', '--lzop'

    elif compression == 'none':
        return '', ''

    raise ValueError('Unknown compression method {}'
                     .format(compression))


def timeit(method):

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        line = '%r (%r, %r) %2.2f sec' % \
            (method.__name__, args, kw, te - ts)

        try:
            logger = args[0].logger
            logger.info(line)
        except BaseException:
            print(line)

        return result

    return timed


def sixdecode(s):
    if isinstance(s, six.string_types):
        return s
    if isinstance(s, six.binary_type):
        return s.decode('utf8')

    raise TypeError("Unknown type of " + str(s))


def shquote(s):
    try:
        import pipes as P
    except ImportError:
        import shlex as P

    return P.quote(s)


duration_regex = re.compile(
    r'((?P<hours>-?\d+?)h)?((?P<minutes>-?\d+?)m)?((?P<seconds>-?\d+?)s)?')

# parse_duration parses strings into time delta values that python can
# deal with.  Examples include 12h, 11h60m, 719m60s, 11h3600s
#


def parse_duration(duration_str):
    parts = duration_regex.match(duration_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for (name, param) in six.iteritems(parts):
        if param:
            time_params[name] = int(param)
    retval = timedelta(**time_params)
    return retval

def parse_verbosity(verbosity=None):
    if verbosity is None:
        return parse_verbosity('info')

    if verbosity == 'True':
        return parse_verbosity('info')

    logger_levels = {
        'debug': 10,
        'info': 20,
        'warn': 30,
        'error': 40,
        'crit': 50
    }

    if isinstance(verbosity, six.string_types) and \
       verbosity in logger_levels.keys():
        return logger_levels[verbosity]
    else:
        return int(verbosity)

def str2duration(s):
    return parse_duration(s.lower())


def rm_rf(path):
    '''
    remove file or a directory
    '''
    if not os.path.exists(path):
        return

    if os.path.isfile(path):
        os.remove(path)  # remove the file
    elif os.path.isdir(path):
        shutil.rmtree(path)  # remove dir and all contains
    else:
        raise ValueError("file {} is not a file or dir.".format(path))

class LogReprinter(object):
    def __init__(self, log_path):
        self.logpath = log_path
        self.logtail = Pygtail(log_path)
        self.is_running = False
        self.tail_thread = None

    def run(self):
        self.tail_thread =\
            threading.Thread(target=self.tail_func, daemon=True)
        self.is_running = True
        self.tail_thread.start()

    def stop(self):
        self.is_running = False
        if self.tail_thread is not None:
            self.tail_thread.join()

    def tail_func(self):
        while self.is_running and self.logtail:
            for line in self.logtail:
                if self.is_running:
                    print(line)
                else:
                    return
            time.sleep(0.1)

