import os
import shutil
import sys
from setuptools import setup, find_packages
from subprocess import call
from setuptools.command.install import install
from setuptools.command.develop import develop

import pkg_resources

import sys
import platform
import ctypes
import pip

# **Python version check**
#
# This check is also made in IPython/__init__, don't forget to update both when
# changing Python version requirements.
if sys.version_info < (3, 4):
    pip_message = 'This may be due to an out of date pip. Make sure you have pip >= 9.0.1.'
    try:
        import pip
        pip_version = tuple([int(x) for x in pip.__version__.split('.')[:3]])
        if pip_version < (9, 0, 1) :
            pip_message = 'Your pip version is out of date, please install pip >= 9.0.1. '\
            'pip {} detected.'.format(pip.__version__)
        else:
            # pip is new enough - it must be something else
            pip_message = ''
    except Exception:
        pass


    error = """
IPython 7.0+ supports Python 3.4 and above.
When using Python 2.7, please install IPython 5.x LTS Long Term Support version.
Python 3.3 was supported up to IPython 6.x.
See IPython `README.rst` file for more information:
    https://github.com/ipython/ipython/blob/master/README.rst
Python {py} detected.
{pip}
""".format(py=sys.version_info, pip=pip_message )

    print(error)
    sys.exit(1)

def read(fname):
    try:
        with open(os.path.join(os.path.dirname(__file__), fname)) as f:
            data = f.read()
            return data
    except BaseException:
        return None


def local_scheme(version):
    if version.distance and version.distance > 0:
        return '.post' + str(version.distance)
    else:
        return ''


def version_scheme(version):
    return str(version.tag)


sys.path.append('studio/')
# This file contains metadata related to the studioml client and python base
# server software


class MyDevelop(develop):
    def run(self):
        call(["pip install -r requirements.txt --no-clean"], shell=True)
        copyconfig()
        develop.run(self)


class MyInstall(install):

    def run(self):
        call(["pip install -r requirements.txt --no-clean"], shell=True)
        copyconfig()
        install.run(self)


def copyconfig():
    config_path = os.path.expanduser('~/.studioml/config.yaml')
    default_config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "studio/default_config.yaml")

    if not os.path.exists(config_path):
        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path))

        shutil.copyfile(
            default_config_path,
            os.path.expanduser('~/.studioml/config.yaml'))


with open('requirements.txt') as f:
    required = f.read().splitlines()

with open('test_requirements.txt') as f:
    test_required = f.read().splitlines()

# projects using the studioml pthon APIs will need to use this installer
# to access the google and AWS cloud storage

setup(
    name='studioml',
    description='TensorFlow model and data management tool',
    packages=find_packages(exclude=['tensorflow']),
    long_description=read('README.rst'),
    url='https://github.com/studioml/studio',
    license='Apache License, Version 2.0',
    keywords='TensorFlow studioml StudioML Studio Keras scikit-learn',
    author='Illia Polosukhin',
    author_email='illia.polosukhin@gmail.com',
    data_files=[('test_requirements.txt')],
    scripts=[
            'studio/scripts/studio',
            'studio/scripts/studio-ui',
            'studio/scripts/studio-run',
            'studio/scripts/studio-serve',
            'studio/scripts/studio-runs',
            'studio/scripts/studio-local-worker',
            'studio/scripts/studio-remote-worker',
            'studio/scripts/studio-start-remote-worker',
            'studio/scripts/studio-add-credentials',
            'studio/scripts/gcloud_worker_startup.sh',
            'studio/scripts/ec2_worker_startup.sh'],
    test_suite='nose.collector',
    tests_require=test_required,
    use_scm_version={
        "version_scheme": version_scheme,
        "local_scheme": local_scheme},
    python_requires='>=3.4',
    setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
    cmdclass={'develop': MyDevelop, 'install': MyInstall},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.6",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Utilities",
        "License :: OSI Approved :: Apache Software License",
    ],
    install_requires=required,
    include_package_data=True,
    zip_safe=False)
