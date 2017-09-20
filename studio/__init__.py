
import fs_tracker
import torch

__version = _read_version()


def _read_version():
    mypath = os.path.dirname(os.path.realpath(__file__))
    try:
        with open(os.path.join(mypath, '.version')) as f:
            ver = f.read()
    except BaseException:
        ver = 'unknown'

    return ver
