Hyperparameter search
=====================

This page describes facilities that Studio provides for
hyperparameter search and optimization.

Basics
------

For now, Studio can launch a batch of experiments using regex
substitution of variables inside the script. These experiments are
launched in a separate project, and can be compared in tensorboard or by
the value of some scalar metrics reported in tensorboard logs.

Consider the following code snippet (code in
`here <https://github.com/studioml/studio/blob/master/examples/keras/train_mnist_keras.py>`__):

::

        lr=0.01
        print('learning rate = {}'.format(lr))
        model.compile(loss='categorical_crossentropy', optimizer=optimizers.SGD(lr=lr))


        # some data preparation code


        tbcallback = TensorBoard(log_dir=fs_tracker.get_tensorboard_dir(),
                         histogram_freq=0,
                         write_graph=True,
                         write_images=False)

        model.fit(
            x_train, y_train, validation_data=(
                x_test,
                y_test),
            epochs=int(sys.argv[1]),
            callbacks=[tbcallback])

We compile a keras model with the specified learning rate for stochastic
gradient descent. What if we want to search a range of learning rates to
determine the best value? (as a side note, in the ``train_mnist_keras.py`` you can
simply use an adaptive learning rate optimizer such as adam to get better
results, but let's forget about that for demonstration purposes)

We can add the following argument to ``studio run`` call:

::

    studio run --hyperparam=lr=0.01:0.01:0.1 train_mnist_keras.py 30

This will create a new project with 10 experiments. For each experiment,
a copy of the working directory will be put in the ``studioml`` cache, and
within each copy of the script
``train_mnist_keras.py`` regex substitution of ``lr`` not followed by
``=`` (i.e. located in right-hand side of an expression) will be performed
to for values from 0.01 to 0.1 with a step size of 0.01. Those
experiments will then be submitted to the queue (to the local queue in the version of the
call above) and executed. The progress of the
experiments can be seen in the Studio WebUI. The last argument ``30`` refers to
number of training epochs, as can be seen in the code snippet above.

Metrics
-------

But wait, do you have to go and check each experiment individually to
figure out which one has done best? Wouldn't it be nice if we could
look at the project and immediately figure out which experiments have
done better than the others? There is indeed such a feature. We can
specify an option ``--metric`` to ``studio run`` to specify which
tensorflow / tensorboard variable to report as a metric, and how to
accumulate it throughout experiment. For keras experiments, that would
most often be ``val_loss``, but in principle any scalar reported in
tensorboard can be used. Note that tensorboard logs need to be written
for this feature to work. Let's modify the command line above a bit:

::

    studio run --hyperparam=lr=0.01:0.01:0.1 --metric=val_loss:min train_mnist_keras.py

This will report the smallest value of ``val_loss`` so far in the projects page
or in the WebUI dashboard. Together with the column sorting feature of the
dashboard you can immediately figure out the best experiment.
The reason why this option is given to the runner and not in the WebUI
after the run is because we are planning to incorporate more complicated
hyperparameter search where new experiments actually depend on
previously seen values of metric. Other allowed values for the
``--metric`` parameter suffix are ":max" for maximum value seen
throughout experiment, or empty for the last value.

Specifying hyperparameter ranges for grid search
------------------------------------------------

Scanning learning rate in constant steps is not always the best idea,
especially if we want to cover several orders of magnitude. We can
specify range with a log step as follows:

::

    --hyperparam=lr=1e-5:l5:0.1

which will make 10 steps spaced logarithmically between 1e-5 and 0.1
(that is, 1e-5, 1e-4, 1e-3, 0.01, 0.1 - matlab style rather than numpy)
Other options are:

1. ``lr=1e-5:10:0.1`` or ``lr=1e-5:u10:0.1`` will generate a uniformly
   spaced grid from 1e-5 to 0.1 (bad idea - the smaller end of the range
   will be spaced very coarsely)

2. ``no_layers=0:3`` or ``nolayers=:3`` will generate uniformly spaced
   grid with a step 1 (0,1,2,3 - endpoints are handled in matlab style,
   not numpy style)

3. ``lr=0.1`` will simply substitute lr with 0.1

4. ``no_layers=2,5,6`` will generate three values - 2,5 and 6

Note that option ``--hyperparam/-hp`` can be used several times for
different hyperparameters; however, keep in mind that grid size grows
exponentially with number of hyperparameters to try.

Specifying hyperparameter ranges for plugin optimizers
------------------------------------------------------
Plugin optimizers are also supported. They can be enabled with the
``-opt/--optimizer`` flag. Either the name of the optimizer (or its file path)
can be specified as argument. The format is slightly different for plugin
optimizers. Below are some examples:

::

    --hyperparam=lr=0:1:10:urla
::

    --hyperparam=lr=0:5:l
::

    --hp=lr=5:5:10:alu

The general format is [min range]:[max range]:{array length}:{flags},
where {array length} and {flags} are optional arguments. The following
flags are supported:

1. {u}: whether or not to constrain hyperparameters to [min range]:[max range]
   (default is constrained).

2. {r}: whether to initialize hyperparameters with random value between
   [min range]:[max range] or right in the middle (default is nonrandom).

3. {l}: whether to use log scaling for the hyperparameter (default is nonlog).

4. {a}: whether the hyperparameter is a numpy array or a scalar. If the
   hyperparameter is a numpy array, then the {array length} field must be
   present as well (default is scalar).

In addition, the python script whose hyperparameters are being optimized must
contain a line with the fitness printed to stdout as shown below. For
hyperparameters whose contents are numpy arrays, they must be loaded using
the ``fs_tracker.get_artifact`` function call as shown below:

::

    from studio import fs_tracker

    lr = np.load(fs_tracker.get_artifact('lr'))

    print "fitness: %s" % np.sum(lr)



Cloud workers
-------------

Waiting till your local machine runs all experiments one after another
can be time consuming. Fortunately, we can outsource the compute to Google
Cloud or Amazon EC2. Please refer to `this page <http://docs.studio.ml/en/latest/cloud.html>`__ for setup
instructions; all the custom hardware configuration options can be
applied to the hyperparameter search as well.

::

    studio run --hyperparam=lr=0.01:0.01:0.1 --metric=val_loss:min --cloud=gcloud --num-workers=4 train_mnist_keras.py

will spin up 4 cloud workers, connect the to the queue and run
experiments in parallel. Beware of spinning up too many workers - if a
worker starts up and finds that everything in the queue is done, it will
(for now) listen to the queue indefinitely waiting for the work, and
won't shut down automatically.
