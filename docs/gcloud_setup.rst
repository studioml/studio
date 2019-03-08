Setting up Google Cloud Compute
===============================

This page describes the process of setting up Google Cloud and
configuring Studio to integrate with it.

Configuring Google Cloud Compute
--------------------------------

Create and select a new Google Cloud project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Go to the Google Cloud console (https://console.cloud.google.com), and
either choose a project that you will use to back cloud
computing or create a new one. If you have not used the Google console
before and there are no projects, there will be a big button "create
project" in the dashboard. Otherwise, you can create a new project by
selecting the drop-down arrow next to current project name in the top
panel, and then clicking the "+" button.

Enable billing for the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Google Cloud computing actually bills you for the compute time you
use, so you must have billing enabled. On the bright side, when you
sign up with Google Cloud they provide $300 of promotional credit, so
really in the beginning you are still using it for free. On the not so
bright side, to use machines with gpus you'll need to show
that you are a legitimate customer and add $35 to your billing account.
In order to enable billing, go to the left-hand pane in the Google Cloud
console, select billing, and follow the instructions to set up your payment
method.

Generate service credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The machines that submit cloud jobs will need to be authorized with
service credentials. Go to the left-hand pane in the Google Cloud console and
select API Manager -> Credentials. Then click the "Create credentials"
button, choose service account key, leave key type as JSON, and in the
"Service account" drop-down select "New service account". Enter a
service account name (the name can be virtually anything and won't
matter for the rest of the instructions). The important part is selecting a
role. Click the "Select a role" dropdown menu, in "Project" select "Service
Account Actor", and then scroll down to "Compute Engine" and select "Compute
Engine Admin (v1)". Then scroll down to "Pub/Sub", and add a role
"Pub/Sub editor" (this is required to create queues, publish and read
messages from them). If you are planning to use Google Cloud storage
(directly, without the Firebase layer) for artifact storage, select the Storage
Admin role as well. You can also add other roles if you are planning to use
these credentials in other applications. When done, click "Create".
Google Cloud console should generate a json credentials file and save it
to your computer.

Configuring Studio
------------------

Adding credentials
~~~~~~~~~~~~~~~~~~

Copy the json file credentials to the machine where Studio will be
run, and create the environment variable ``GOOGLE_APPLICATION_CREDENTIALS``
that points to it. That is, run

::

    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

Note that this variable will be gone when you restart the terminal, so
if you want to reuse it, add it to ``~/.bashrc`` (linux) or
``~/.bash_profile`` (OS X)

Modifying the configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the config file (the one that you use with the ``--config`` flag, or, if you
use the default, in the ``studio/default_config.yaml``), go to the ``cloud``
section. Change projectId to the project id of the Google project for which
you enabled cloud computing. You can also modify the default instance
parameters (see `Cloud computing for studio <http://docs.studio.ml/en/latest/cloud.html>`__ for
limitations though).

Test
~~~~

To test if things are set up correctly, go to
``studio/examples/general`` and run

::

    studio run --cloud=gcloud report_system_info.py

Then run ``studio`` locally, and watch the new experiment. In a little
while, it should change its status to "finished" and show the system
information (number of cpus, amount of ram / hdd) of a default instance.
See `Cloud computing for studio <http://docs.studio.ml/en/latest/cloud.html>`__ for more instructions on
using an instance with specific hardware parameters.
