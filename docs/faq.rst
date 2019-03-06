Frequently Asked Questions
==========================

`Join us on Slack! <https://studioml.now.sh/>`_
-----------------------------------------------

- `What is the complete list of tools Studio.ML is compatible with?`_

- `Is Studio.ML compatible with Python 3?`_

- `Do I need to change my code to use Studio.ML?`_

- `How can I track the training of my models?`_

- `How does Studio.ml integrate with Google Cloud or Amazon EC2?`_

- `Is it possible to view the experiment artifacts outside of the Web UI?`_


_`What is the complete list of tools Studio.ML is compatible with?`
------------------------------------------------------------------

Keras, TensorFlow, PyTorch, scikit-learn, pandas - anything that runs in python

_`Is Studio.ML compatible with Python 3?`
--------------------------------

Yes! Studio.ML is now compatible to use with Python 3. 

_`Can I use Studio.ML with my jupyter / ipython notebooks?`
-----------------------------------------------------------

Yes! The basic usage pattern is import ``magics`` module from studio, 
and then annotate cells that need to be run via studio with 
``%%studio_run`` cell magic (optionally followed by the same command-line arguments that 
``studio run`` accepts. Please refer to `<jupyter.rst>` the for more info


_`Do I need to change my code to use Studio.ML?`
---------------------------------------------

Studio is designed to minimize any invasion of your existing code. Running an experiment with Studio should be as simple as replacing ``python`` with ``studio run`` in your command line with a few flags for capturing your workspace or naming your experiments.

_`How can I track the training of my models?`
--------------------

You can manage any of your experiments- current, old or queued- through the web interface. Simply run ``studio ui`` to launch the UI to view details of any of your experiments.

_`How does Studio.ml integrate with Google Cloud or Amazon EC2?`
-----------------

We use standard Python tools like Boto and Google Cloud Python Client to launch GPU instances that are used for model training and de-provision them when the experiment is finished.

_`Is it possible to view the experiment artifacts outside of the Web UI?`
-------------------

Yes! 

::
       
    from studio import model

    with model.get_db_provider() as db:
        experiment = db.get_experiment(<experiment_key>)


will return an experiment object that contains all the information about the experiment with key ``<experiment key>``, including artifacts. 
The artifacts can then be downloaded: 

::

    with model.get_db_provider() as db:
        artifact_path = db.get_artifact(experiment.artifacts[<artifact-tag>])

will download an artifact with tag ``<artifact-tag>`` and return a local path to it in ``artifact_path`` variable

