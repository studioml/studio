Setting up a remote worker
==========================

This page describes a procedure for setting up a remote worker for
Studio. Remote workers listen to the queue; once a worker
receives a message from the queue, it starts the experiments.

Getting credentials
-------------------

1. Remote workers work by listening to a distributed queue. Right now the
   distributed queue is backed by Google PubSub, so to access it you'll
   need application credentials from Google (in the future, it may be
   implemented via Firebase itself, in which case this step should
   become obsolete). If you've made it this far, you are likely to have a
   Google Cloud Compute account set up, but if not, go to
   http://cloud.google.com and either set up an account or sign in.
2. Next, create a project if you don't have a project corresponding to
   Studio just yet.
3. Then go to API Manager -> Credentials, and click "Create credentials"
   -> "Service account key"
4. Choose "New service account" from the "Select accout" dropdown, and
   keep key type as JSON.
5. Enter a name of your liking for the account (Google will convert it to a
   unique name), and choose "PubSub Editor" for a role (technically, you
   can create 2 keys, and keep the publisher on a machine that submits work,
   and subscriber key on a machine that implements the work). If you are
   planning to use cloud workers, it is also recommended to add Compute
   Engine / Compute Engine Admin (v1).
6. Save a json credentials file. It is recommended that the credential
   file be saved in a safe location such as your ~/.ssh directory and
   that you use the 'chmod 0600 file.json' command to help secure the
   file within your Linux user account.
7. Add the ``GOOGLE_APPLICATION_CREDENTIALS`` variable to the environment
   that points to the saved json credentials file both on the work submitter
   and work implementer.

Enabling Google PubSub for the Google Application
-------------------------------------------------

In order to use Google queues for your own remote workers, as opposed to
the Google Cloud Platform workers, PubSub API services will need to be
enabled for the project. To do this go to the Google API Manager
Dashboard within the Google Cloud Platform console and select the Enable
API drop down, which is located at the top of the Dashboard with a '+'
icon beside it. From here you will see a panel of API services that can
be enabled, choose the PubSub API. In the PubSub Dashboard there is an
option to enable the API at the top of the Dashboard.

Setting up remote worker
------------------------

If you don't have your own docker container to run jobs in, follow the
instructions below. Otherwise, jump to the next section. 

1. Install docker, and nvidia-docker to use gpus 

2. Clone the repo ::

        git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e .

   To check the success of the installation, you can run ``python $(which nosetests) --processes=10 --process-timeout=600`` to run the tests (may take about 10 min to finish)

3. Start the worker (queue name is a name of the queue that will define
   where submit work to) ::

       studio start remote worker --queue=<queue-name>

Setting up a remote worker with exising docker image
----------------------------------------------------

This section applies when you already have a docker
image/container and would like the Studio remote worker to run inside it.

1. Make sure that the image has python-dev, python-pip, and git installed,
   as well as Studio. The easiest way is to make your Dockerfile inherit
   from from the Studio Dockerfile (located in the Studio root
   directory). Otherwise, copy relevant contents of Studio Dockerfile
   into yours.
2. Bake the credentials into your image. Run ::

       studio add credentials [--base_image=<image>] [--tag=<tag>] [--check-gpu]

   where ``<image>`` is the name of your image (default is peterzhokhoff/studioml); ``<tag>`` is the tag of the image with credentials (default is ``<image>_creds``). Add option check-gpu if you are planning to use image on the same machine you are running the script from. This will check for presence of the CUDA toolbox and uninstall tensorflow-gpu if not found.

3. Start the remote worker passing ``--image=<tag>``: ::

       studio start remote worker --image=<tag> --queue=<queue-name>

   You can also start the container and remote worker within it manually, by running: ::

        studio remote worker --queue=<queue-name> 

   within the container - this is essentially what the ``studio-start-remote-worker`` script does, plus mounting cache directories ``~/.studioml/experiments`` and ``~/.studioml/blobcache``

Submitting work
------------------

On a submitting machine (usually local):

::

    studio run --queue <queue-name> <any_other_args> script.py <script_args>

This script should quit promptly, but you'll be able to see experiment
progress in the Studio WebUI.

