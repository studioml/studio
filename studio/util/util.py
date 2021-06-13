import hashlib
from io import StringIO
from datetime import timedelta
import re
import random
import string
import time
import sys
import shutil
import shlex
import os
import tempfile
import uuid

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
    return filehash(filename, block_size, hashobj=None)


def filehash(filename, block_size=65536, hashobj=None):
    if hashobj is None:
        hashobj = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            hashobj.update(block)
    return hashobj.hexdigest()


def rand_string(length):
    return "".join([random.choice(string.ascii_letters + string.digits)
                    for n in range(length)])


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
        except exception_class as exc:
            check_for_kb_interrupt()
            if i == no_retries - 1:
                raise exc

            if logger:
                logger.info(
                    ('Exception {0} is caught, ' +
                     'sleeping {1}s and retrying (attempt {2} of {3})')
                        .format(exc, sleep_time, i, no_retries))
            time.sleep(sleep_time)
    return None


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

    if compression == 'gzip':
        return '.gz', '--gzip'

    if compression == 'xz':
        return '.xz', '--xz'

    if compression == 'lzma':
        return '.lzma', '--lzma'

    if compression == 'lzop':
        return '.lzop', '--lzop'

    if compression == 'none':
        return '', ''

    raise ValueError('Unknown compression method {}'
                     .format(compression))


def timeit(method):
    def timed(*args, **kw):
        tstart = time.time()
        result = method(*args, **kw)
        tend = time.time()

        line = '%r (%r, %r) %2.2f sec' % \
               (method.__name__, args, kw, tend - tstart)

        try:
            logger = args[0].logger
            logger.info(line)
        except BaseException:
            check_for_kb_interrupt()
            print(line)

        return result

    return timed


def sixdecode(sval):
    if isinstance(sval, str):
        return sval
    if isinstance(sval, bytes):
        return sval.decode('utf8')
    raise TypeError("Unknown type of " + str(sval))


def shquote(sval):
    return shlex.quote(sval)


duration_regex = re.compile(
    r'((?P<hours>-?\d+?)h)?((?P<minutes>-?\d+?)m)?((?P<seconds>-?\d+?)s)?')


# parse_duration parses strings into time delta values that python can
# deal with.  Examples include 12h, 11h60m, 719m60s, 11h3600s
#


def parse_duration(duration_str):
    parts = duration_regex.match(duration_str)
    if not parts:
        return None
    parts = parts.groupdict()
    time_params = {}
    for (name, param) in parts.items():
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

    if isinstance(verbosity, str) and \
            verbosity in logger_levels.keys():
        return logger_levels[verbosity]
    return int(verbosity)


def str2duration(sval):
    return parse_duration(sval.lower())


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
    except BaseException:
        check_for_kb_interrupt()

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

def add_packages(list1, list2):
    # This function dedups the package names which I think could be
    # functionally not desirable however rather than changing the behavior
    # instead we will do the dedup in a stable manner that prevents
    # package re-ordering
    pkgs = {re.sub('==.+', '', pkg): pkg for pkg in list1 + list2}
    merged = []
    for k in list1 + list2:
        val = pkgs.pop(re.sub('==.+', '', k), None)
        if val is not None:
            merged.append(val)
    return merged
