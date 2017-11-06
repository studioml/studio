import os
from setuptools_scm import get_version

from . import fs_tracker

__version__ = get_version(root='..', relative_to=__file__)
# from . import torch
