import fs_tracker
import torch
import os


def _read_version():
    mypath = os.path.dirname(os.path.realpath(__file__))
    try:
        with open(os.path.join(mypath, '.version')) as f:
            ver = f.read()
    except BaseException:
        ver = 'unknown'

    return ver


__version__ = _read_version()
