import os
import shutil
import sys
from setuptools import setup, find_packages
from subprocess import call
from setuptools.command.install import install
from setuptools.command.develop import develop


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
        # print " >>> MyDevelop with verison {} <<< ".format(VERSION)
        call(["pip install -r requirements.txt --no-clean"], shell=True)
        copyconfig()
        develop.run(self)


class MyInstall(install):

    def run(self):
        # print " >>> MyInstall with verison {} <<< ".format(VERSION)
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
    # Add the tensorflow python package as a dependency for the studioml
    # python modules but be selective about whether the GPU version is used
    # or the default CPU version.  Not doing this will result in the CPU
    # version taking precedence in many cases.

with open('test_requirements.txt') as f:
    test_required = f.read().splitlines()

# projects using the studioml pthon APIs will need to use this installer
# to access the google and AWS cloud storage

setup(
    name='studioml',
    # version=VERSION,
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
    setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
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
    include_package_data=True,
    zip_safe=False)
