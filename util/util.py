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
import requests
import six
import tempfile
import uuid

from storage.storage_type import StorageType

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


def report_fatal(msg: str, logger):
    logger.error(msg)
    raise ValueError(msg)


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
            check_for_kb_interrupt()
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


def download_file(url, local_path, logger=None):
    if url.startswith('s3://'):
        raise NotImplementedError('util.download_file() NOT implemented for s3 endpoints.')

    response = requests.get(
        url,
        stream=True)
    if logger:
        logger.info(("Trying to download file at url {0} to " +
                     "local path {1}").format(url, local_path))

    if response.status_code == 200:
        try:
            with open(local_path, 'wb') as f:
                for chunk in response:
                    f.write(chunk)
            return True
        except Exception as exc:
            msg: str = 'Download/write {0} from {1} FAILED: {2}.' \
                .format(local_path, url, exc)
            if logger:
                logger.error(msg)
            return False

    elif logger:
        msg: str = 'Download {0} from {1}: Response error with code {2}.' \
            .format(local_path, url, response.status_code)
        logger.error(msg)
        return False

def upload_file(url, local_path, logger=None):
    if logger:
        logger.info(("Trying to upload file {0} to " +
                     "url {1}").format(local_path, url))
    tic = time.time()
    try:
        with open(local_path, 'rb') as f:
            resp = requests.put(url, data=f)
    except Exception as exc:
        msg: str = 'Upload {0} to {1} FAILED: {2}. Aborting.' \
            .format(local_path, url, exc)
        report_fatal(msg, logger)

    if resp.status_code != 200 and logger:
        msg: str = 'Upload {0} to {1}: Response error {2}:{3}. Aborting.' \
            .format(local_path, url, resp.status_code, resp.reason)
        report_fatal(msg, logger)

    if logger:
        logger.debug('File {0} upload to {1} done in {2} s'
                     .format(local_path, url, time.time() - tic))


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


def parse_s3_path(qualified: str):
    qualified_split = qualified.split('/')
    if _looks_like_url(qualified_split[2]):
        url = qualified_split[2]
        bucket = qualified_split[3]
        key = '/'.join(qualified_split[4:])
    else:
        url = None
        bucket = qualified_split[2]
        key = '/'.join(qualified_split[3:])
    return url, bucket, key

def retry(f,
          no_retries=5, sleep_time=1,
          exception_class=BaseException, logger=None):
    for i in range(no_retries):
        try:
            return f()
        except exception_class as e:
            check_for_kb_interrupt()
            if i == no_retries - 1:
                raise e

            if logger:
                logger.info(
                    ('Exception {0} is caught, ' +
                     'sleeping {1}s and retrying (attempt {2} of {3})')
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
            check_for_kb_interrupt()
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


def get_temp_filename() -> str:
    return os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))

def delete_local_path(local_path: str, root: str, shallow: bool):
    if local_path is None or len(local_path) == 0:
        return
    if not (os.path.exists(local_path) and os.path.isfile(local_path)):
        return
    folder_path, _ = os.path.split(local_path)
    os.remove(local_path)
    if not shallow:
        delete_local_folders(folder_path, root)

def delete_local_folders(local_folder_path: str, root: str):
    if local_folder_path == root:
        return
    if len(os.listdir(local_folder_path)) > 0:
        return
    head, _ = os.path.split(local_folder_path)
    try:
        os.rmdir(local_folder_path)
    except:
        check_for_kb_interrupt()
        pass
    delete_local_folders(head, root)

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
        raise ValueError("file {0} is not a file or dir.".format(path))

def check_for_kb_interrupt():
    current_exc = sys.exc_info()[1]
    if current_exc is None:
        return
    if isinstance(current_exc, KeyboardInterrupt):
        raise current_exc
    return

