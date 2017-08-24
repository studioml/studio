import os
import shutil
from setuptools import setup
from subprocess import call
from setuptools.command.install import install
from setuptools.command.develop import develop

VERSION = ""

# This file contains metadata related to the studioml client and python base
# server software


class MyDevelop(develop):
    def run(self):
        if "TRAVIS_TAG" in os.environ:
          global VERSION
          VERSION = os.environ["TRAVIS_TAG"]
        call(["pip install -r requirements.txt --no-clean"], shell=True)
        copyconfig()
        develop.run(self)


class MyInstall(install):
    if "TRAVIS_TAG" in os.environ:
      global VERSION
      VERSION = os.environ["TRAVIS_TAG"]
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


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


with open('requirements.txt') as f:
    required = f.read().splitlines()

# projects using the studioml pthon APIs will need to use this installer
# to access the google and AWS cloud storage

setup(
    name='studioml',
    version=VERSION,
    description='TensorFlow model and data management tool',
    packages=['studio'],
    long_description=read('README'),
    url='https://github.com/studioml/studio',
    license='Apache License, Version 2.0',
    keywords='TensorFlow studioml StudioML Studio Keras scikit-learn',
    author='Illia Polosukhin',
    author_email='illia.polosukhin@gmail.com',
    #        data_files=[('bin', ['studio/scripts/*'])],
    scripts=[
            'studio/scripts/studio',
            'studio/scripts/studio-ui',
            'studio/scripts/studio-run',
            'studio/scripts/studio-runs',
            'studio/scripts/studio-local-worker',
            'studio/scripts/studio-remote-worker',
            'studio/scripts/studio-start-remote-worker',
            'studio/scripts/studio-add-credentials',
            'studio/scripts/gcloud_worker_startup.sh',
            'studio/scripts/ec2_worker_startup.sh'],
    tests_suite='nose.collector',
    tests_require=['nose'],
    cmdclass={'develop': MyDevelop, 'install': MyInstall},
    classifiers=[
            "Development Status :: 3 - Alpha",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "Operating System :: POSIX :: Linux",
            "Programming Language :: Python",
            "Topic :: Scientific/Engineering :: Artificial Intelligence",
            "Topic :: Utilities",
            "License :: OSI Approved :: Apache Software License",
    ],
    install_requires=required,
    zip_safe=False)
