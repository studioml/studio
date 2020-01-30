Installation
============

Installation Packaging
----------------------

pip install ``studioml`` from the master pypi repositry:

::

    pip install studioml

or, install the source and development environment for Studio from the git project directory:

::

    git clone https://github.com/studioml/studio && cd studio && pip install -e .

A setup.py is included in the top level of the git repository to
allow the creation of tar archives for installation on runners and
other systems where git is not the primary means of handling Python
artifacts. To create the installable, use the following command from the
top level directory of a cloned repository:

::

    python setup.py sdist

This command will create a file dist/studio-x.x.tar.gz that can be used
with pip as follows:

::

    pip install studio-x.x.tar.gz

Certain types of runners can make use of the Studio software
distribution to start projects without any intervention, i.e. devops-less
runners. To include the software distribution, add the tar.gz file to
your workspace directory under a dist subdirectory. Runners supporting
software distribution will unroll the software and install it using
virtualenv.

We recommend setting up a `virtual
environment <https://github.com/pypa/virtualenv>`__.

CI/CD pipeline
----------------------

The Studio project distributes official releases using a travis based
build and deploy pipeline. The Travis project that builds the official
github repository for Studio has associated encrypted user and
password credentials that the Travis .yml file refers to. These secrets
can be updated using the Travis configuration found at
https://travis-ci.com/SentientTechnologies/studio/settings. The
PYPI\_PASSWORD and PYPI\_USER variables should point at an owner account
for the project. To rotate these values, remove the old ones using the
settings page and re-add the same variables with new values.

When code is pushed to the master branch in the github repository, a
traditional build will be performed by Travis. To push a release after
the build is complete, add a server compatible version number as a tag
to the repository and do a 'git push --tags' to trigger the deployment
to pypi. Non-tagged builds are never pushed to pypi. Any tag will result
in a push to pypi, so care should be taken to manage the visible
versions using the PYPI\_USER account.

Release process
----------------------

Studio is released as a binary or source distribution using a hosted
package at pypi.python.org. To release Studio, you must have
administrator role access to the Studio Package on the
https://pypi.python.org/ web site. Releases are done using the setup
packaging found inside the setup.py files.

When working with the pypi command line tooling you should create a
~/.pyirc file with your account details, for example:

::

    [distutils]
    index-servers=
        pypi
        testpypi

    [testpypi]
    repository = https://testpypi.python.org/pypi
    username = {your pipy account}
    password = {your password}

    [pypi]
    username = {your pipy account}

The command to push a release is as follows.

::
    pip install twine
    python setup.py sdist bdist_wheel
    twine upload dist/*

If you wish to test releases and not pollute our pypi production release
train and numbering, please use the '-r' option to specify the test pypi
repository. pypi releases are idempotent.

Running tests
----------------------

To run the unit and regression tests, run

::

    python $(which nosetests) --processes=8 --process-timeout=600

Note that simply running ``nosetests`` tends to not use virtualenv
correctly. If you have application credentials configured to work with
distributed queues and cloud workers, those will be tested as well.
Otherwise, such tests will be skipped. The total test runtime,
when run in parallel as in the command above, should be no more than 10
minutes. Most of the tests are I/O limited, so parallel execution speeds
up things quite a bit. The longest test is the gpu cloud worker test in
EC2 cloud (takes about 500 seconds due to installation of the drivers /
CUDA on the EC2 instance).


