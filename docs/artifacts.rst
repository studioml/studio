Artifact management
===================

This page describes facilities that Studio provides for
management of experiment artifacts. For now, artifact storage is backed
by google cloud storage.

Basic usage
-----------

The idea behind artifact management is three-fold: 

1. With no coding overhead capture the data that experiment depends on (e.g. dataset). 

2. With no coding overhead save and with minimal overhead visualize the results of the experiment (neural network weights, etc). 

3. With minimal coding overhead make experiments reproducible on any machine (without manual data download, path correction etc).

Below we provide the examples of each use case.

Capture data
~~~~~~~~~~~~

Let's imagine that file ``train_nn.py`` in current directory trains
neural network based on data located in ``~/data/``. In order to capture
the data, we need to invoke ``studio run`` as follows:

::

    studio run --capture-once=~/data:data train_nn.py

Flag ``--capture-once`` (or ``-co``) specifies that data at path ~/data
needs to be captured once at the experiment startup. Additionally, tag
``data`` (provided as a value after ``:``) allows script to access data
in a machine-independent way; and also distinguishes the dataset in the
web-ui (Web UI page of the experiment will contain download link for
tar-gzipped folder ``~/data``)

Save the result of the experiment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's now consider an example of a python script that periodically saves
some intermediate data (e.g. weigths of a neural network). The following
example can be made more consise using keras or tensorflow built-in
checkpointers, but we'll leave that as an exercise for the reader.
Consider the following contents of file ``train_linreg.py`` (also
located in studio/helloworld/ in repo):

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
problem by gradient descent method and saving weights at each step to
~/weights folder.

In order to simply save the weigths, we can run the following command:

::

    studio run --capture=~/weights:weights train_linreg.py 

Flag ``--capture`` (or ``-c``) specifies that data from folder
``~/weights`` needs to be captured continously - every minute (frequency
can be changed in a config file), and at the end of the experiment. In
the Web ui page of the experiment we now have a link to weights
artifact. This simple script should finish almost immediately, but for
longer running jobs upload happens every minute of a runtime (the upload
happens in a separate thread, so this should not slow down the actual
experiment)

Machine-independent access to the artifacts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

So far we have been assuming that all the experiments are being run a
local machine; and the only interaction with artifacts has been to save
them for posterity's sake. But what if our experiments are growing a bit
to big to be run locally? Fortunately, studio comes with a dockerized
worker that can run your jobs on a beefy gpu server, or on a cloud
instance (cloud management is not provided just yet). But how do we make
local data available on such worker? Clearly, a local path along the
lines of ``/Users/john.doe/weights/`` will not always be reproducible on
a remote worker. Studio provides a way to access files in a
machine-independent way, as follows. Let us replace last three lines in
the script above by:

::

    from studio import fs_tracker 
    with open(os.path.join(fs_tracker.get_artifact('weights'), 
                          'lr_w_{}_{}.pck'.format(step, loss)),
            'w') as f:
        f.write(pickle.dumps(w))

We can now run the script either locally, the exact same way as before:

::

    studio run --capture=~/weights:weights train_linreg.py 

Or, if the have a worker listening to the queue ``work_queue``:

::

    studio run --capture=~/weights:weights --queue work_queue train_linreg.py

In the former case, the call ``fs_tracker.get_artifact('weights')`` will
simply return ``os.path.expanduser('~/weights')``. In the latter case,
remote worker will set up a cache directory that corresponds to artifact
with tag weights, copies existing data from storage into it (so that
data can be read from that directory as well), and the call
``fs_tracker.get_artifact('weights')`` will return path to that
directory. In both cases, --experiment flag is not mandatory, if you
don't speco

Re-using artifacts from other experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A neat side-benefit of using machine-indepdent access to the artifacts
is ability to plug different datasets into experiment without touching
the script at all - simply provide different paths for the same tag in
--capture(-once) flags. More importantly though, one can reuse datasets
(or any artifacts) from another experiment using --reuse flag. First,
let's imagine we run the ``train_linreg.py`` script, this time giving
experiment a name:

::

    studio run --capture=~/weights:weights --experiment linear_regression train_linreg.py 

Say, now we want to print the L2 norm of the last set of weights. Let's
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

Flag reuse tells studio run that artifact ``weights`` from experiment
``linear_regression`` will be used in the current experiment with a tag
``w``. There is a bit of a catch - for download optimization, all
artifacts from other experiments are considered immutable, and cached as
such. If you re-run the experiment with the same name and would like to
use new artifacts from it, clean the cache folder
``~/.studioml/blobcache/``.

Default artifacts
-----------------

Each experiment gets default artifacts that it can use via
``fs_tracker.get_artifact()`` even without --reuse or --capture(-once)
flags. Those are:

1. ``workspace``- this artifact always gets cached to/from ``.`` folder, thus creating a copy of working directory on a remote machine; and saving state of the scripts

#. ``output``- this artifact is a file with stdout and stderr of the script run

#. ``modeldir``- it is recommended to save weights in this directory, because studio will try to do some analysis on it, such as number of checkpoints etc.

#. ``tb``- it is recommended to save tensorboard logs into this directory, this way studio will be able to automatically feed them into tensorboard

All of the default artifacts are considered mutable (i.e. are stored
continously). The default artifacts can be overwritten by
--capture(-once) flags.

Custom storage
--------------

Firebase API is great for small projects, but it is easy to grow beyond
limits of free storage in it (5 Gb as of 08/02/2017), after which it
becomes really expensive. StudioML can utilize google cloud
storage for artifact storage directly if your projects don't fit into
firebase (support of Amazon S3 is on the way). 

For now the downside of using google cloud storage is that google service account credentials
are used, which means that all users in possession of the credentials
file have read/write access to the objects in the storage, so in
principle one user can delete experiments of another. See
`here <gcloud_setup.rst>`__ for instructions on how to generate service
account credentials. Once you have credentials file generated, uncomment
"storage" section in your config.yaml file, set type of storage to
``gcloud``, and specify storage bucket. Note that bucket name needs to
be unique, and the error will be thrown if bucket with that name cannot
be created. Thus the safest way is to create bucket manually from the
google cloud console, and then specify it in config.yaml. Folder/file
structure within the bucket is the same as for firebase storage, so if
you want to migrate all your firebase experiments to the new storage,
you can copy the firebase storage bucket and point config.yaml to the
copy (you could point config.yaml to the original, but then you'll be
paying the same Firebase prices).
