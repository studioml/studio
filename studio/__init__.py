from setuptools_scm import get_version

try:
    __version__ = get_version(root='..', relative_to=__file__)
except BaseException:
    pass

# from . import torch
