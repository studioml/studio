import os
import shutil
from setuptools import setup
from subprocess import call
from setuptools.command.install import install
from setuptools.command.develop import develop

# This file contains metadata related to the tfstudio client and python base
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
    config_path = os.path.expanduser('~/.tfstudio/config.yaml')
    default_config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "studio/default_config.yaml")

    if not os.path.exists(config_path):
        if not os.path.exists(os.path.dirname(config_path)):
                os.makedirs(os.path.dirname(config_path))

        shutil.copyfile(
            default_config_path,
            os.path.expanduser('~/.tfstudio/config.yaml'))


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


with open('requirements.txt') as f:
    required = f.read().splitlines()

# projects using the tfstudio pthon APIs will need to use this installer
# to access the google and AWS cloud storage

setup(
    name='studio',
    version='0.0',
    description='TensorFlow model and data management tool',
    packages=['studio'],
    long_description=read('README.md'),
    url='https://github.com/ilblackdragon/studio',
    author='Illia Polosukhin',
    author_email='ilblackdragon@XIX.ai',
    #        data_files=[('bin', ['studio/scripts/*'])],
    scripts=[
            'studio/scripts/studio',
            'studio/scripts/studio-ui',
            'studio/scripts/studio-run',
            'studio/scripts/studio-local-worker',
            'studio/scripts/studio-remote-worker',
            'studio/scripts/studio-start-remote-worker',
            'studio/scripts/studio-add-credentials',
            'studio/scripts/gcloud_worker_startup.sh',
            'studio/scripts/ec2_worker_startup.sh'],
    tests_suite='nose.collector',
    tests_require=['nose'],
    cmdclass={'develop': MyDevelop, 'install': MyInstall},
    install_requires=required,
    zip_safe=False)
