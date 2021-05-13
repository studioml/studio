Artifact management
===================

This page describes facilities that Studio provides for
management of experiment artifacts. For now, artifact storage is backed
by Google Cloud storage.

Basic usage
-----------

The goal of artifact management is three-fold:

1. With no coding overhead capture data the experiment depends on (e.g. dataset).

2. With no coding overhead save, and with minimal overhead visualize, the results of the experiment (neural network weights, etc).

3. With minimal coding overhead make experiments reproducible on any machine (without manual data download, path correction etc).

Below we provide the examples of each use case.

Capture data
~~~~~~~~~~~~

Let's imagine that file ``train_nn.py`` in the current directory trains a
neural network based on data located in ``~/data/``. In order to capture
the data, we need to invoke ``studio run`` as follows:

::

    studio run --capture-once=~/data:data train_nn.py

Flag ``--capture-once`` (or ``-co``) specifies that data at path ~/data
needs to be captured once at experiment startup. Additionally, the tag
``data`` (provided as a value after ``:``) allows the script to access data
in a machine-independent way, and also distinguishes the dataset in the
web-ui (the Web UI page of the experiment will contain download link for
tar-gzipped folder ``~/data``).

Save the result of the experiment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's now consider an example of a python script that periodically saves
some intermediate data (e.g. weights of a neural network). The following
example can be made more concise using the keras or tensorflow built-in
checkpointers, but we'll leave that as an exercise for the reader.
Consider the following contents of file ``train_linreg.py`` (also
located in ``studio/examples/general/`` in repo):

::

    import numpy as np
    import pickle
    import os

    no_samples = 100
    dim_samples = 5

    learning_rate = 0.01
    no_steps = 10

    X = np.random.random((no_samples, dim_samples))
    y = np.random.random((no_samples,))

    w = np.random.random((dim_samples,))

    for step in range(no_steps):
        yhat = X.dot(w)
        err = (yhat - y)
        dw = err.dot(X)
        w -= learning_rate * dw
        loss = 0.5 * err.dot(err)

        print("step = {}, loss = {}, L2 norm = {}".format(step, loss, w.dot(w)))

        with open(os.path.expanduser('~/weights/lr_w_{}_{}.pck'.format(step, loss)), 'w') as f:
            f.write(pickle.dumps(w))


The reader can immediately see that we are solving a linear regression
problem by gradient descent and saving weights at each step to
~/weights folder.

In order to simply save the weigths, we can run the following command:

::

    studio run --capture=~/weights:weights train_linreg.py

Flag ``--capture`` (or ``-c``) specifies that data from folder
``~/weights`` needs to be captured continously - every minute (the frequency
can be changed in a config file), and at the end of the experiment. In
the Web ui page of the experiment we now have a link to weights
artifact. This simple script should finish almost immediately, but for
longer running jobs upload happens every minute of runtime (the upload
happens in a separate thread, so this should not slow down the actual
experiment).

Machine-independent access to the artifacts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

So far we have been assuming that all experiments are being run on a
local machine, and the only interaction with artifacts has been to save
them for posterity's sake. But what if our experiments are growing a bit
too big to be run locally? Fortunately, Studio comes with a dockerized
worker that can run your jobs on a beefy gpu server, or on a cloud
instance. But how do we make
local data available to such a worker? Clearly, a local path along the
lines of ``/Users/john.doe/weights/`` will not always be reproducible on
a remote worker. Studio provides a way to access files in a
machine-independent way, as follows. Let us replace the last three lines in
the script above by:

::

    from studio import fs_tracker
    with open(os.path.join(fs_tracker.get_artifact('weights'),
                          'lr_w_{}_{}.pck'.format(step, loss)),
            'w') as f:
        f.write(pickle.dumps(w))

We can now run the script locally, the exact same way as before:

::

    studio run --capture=~/weights:weights train_linreg.py

Or, if we have a worker listening to the queue ``work_queue``:

::

    studio run --capture=~/weights:weights --queue work_queue train_linreg.py

In the former case, the call ``fs_tracker.get_artifact('weights')`` will
simply return ``os.path.expanduser('~/weights')``. In the latter case, a
remote worker will set up a cache directory that corresponds to the artifact
tagged as ``weights`` and copy existing data from studio.storage into it (so that
data can be read from that directory as well). The call
``fs_tracker.get_artifact('weights')`` will return the path to that
directory. In both cases, the ``--experiment`` flag is not mandatory; if you don’t specify a name,
a random uuid will be generated.

Re-using artifacts from other experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A neat side-benefit of using machine-independent access to the artifacts
is the ability to plug different datasets into an experiment without touching
the script at all - simply provide different paths for the same tag in the
``--capture(-once)`` flags. More importantly, one can reuse datasets
(or any artifacts) from another experiment using the ``--reuse`` flag. First,
let's imagine we've run the ``train_linreg.py`` script, this time giving the
experiment a name:

::

    studio run --capture=~/weights:weights --experiment linear_regression train_linreg.py

Say we now want to print the L2 norm of the last set of weights. Let's
consider the following script (``print_norm_linreg.py``):

::

    import glob
    import os
    from studio import fs_tracker
    import pickle


    weights_list = glob.glob(os.path.join(fs_tracker.get_artifact('w'),'*.pck'))
    weights_list.sort()

    print('*****')
    print(weights_list[-1])
    with open(weights_list[-1], 'r') as f:
        w = pickle.load(f)

    print w.dot(w)
    print('*****')

We can run it via

::

    studio run --reuse=linear_regression/weights:w print_norm_linreg.py

The flag ``reuse`` tells ``studio run`` that artifact ``weights`` from experiment
``linear_regression`` will be used in the current experiment with a tag
``w``. There is a bit of a catch - for download optimization, all
artifacts from other experiments are considered immutable, and cached as
such. If you re-run the experiment with the same name and would like to
use new artifacts from it, clean the cache folder
``~/.studioml/blobcache/``.

Default artifacts
-----------------

Each experiment gets default artifacts that it can use via
``fs_tracker.get_artifact()`` even without the ``--reuse`` or ``--capture(-once)``
flags. Those are:

1. ``workspace``- this artifact always gets cached to/from ``.`` folder, thus creating a copy of the working directory on a remote machine and saving the state of the scripts

#. ``output``- this artifact is a file with the stdout and stderr produced by running the script

#. ``modeldir``- it is recommended to save weights to this directory because Studio will try to do some analysis on it, such as count the number of checkpoints etc.

#. ``tb``- it is recommended to save Tensorboard logs to this directory, this way Studio will be able to automatically feed them into Tensorboard

All of the default artifacts are considered mutable (i.e. are stored
continously). The default artifacts can be overwritten by
--capture(-once) flags.

Ignoring Files
--------------

By placing an .studioml_ignore file inside the directory of the script invoked by studio run, you can specify certain directories or files to avoid being uploaded. These files will not exist in the workspace directory when the script is running remotely.

Custom storage
--------------

The Firebase API is great for small projects, but it is easy to grow beyond its
free storage limits (5 Gb as of 08/02/2017), after which it
becomes very expensive. Studio can utilize Google Cloud
storage directly for artifact storage if your projects don't fit into
Firebase (support for Amazon S3 is on the way).

For now, the downside of using Google Cloud storage is that Google service account credentials
are used, which means that all users in possession of the credential's
file have read/write access to the objects in the storage, so in
principle one user can delete the experiments of another. See
`here <http://docs.studio.ml/en/latest/gcloud_setup.html>`__ for instructions on how to generate service
account credentials. Once you have generated a credentials file, uncomment the
"storage" section in your config.yaml file, set the type of storage to
``gcloud``, and specify a storage bucket. Note that the bucket name needs to
be unique, and an error will be thrown if a bucket with that name cannot
be created. The safest approach is to create a bucket manually from the
Google Cloud console, and then specify it in config.yaml. Folder/file
structure within the bucket is the same as for Firebase storage, so if
you want to migrate all your Firebase experiments to the new storage
you can copy the Firebase storage bucket and point config.yaml to the
copy (you could point config.yaml to the original, but then you'll be
paying the same Firebase prices).
