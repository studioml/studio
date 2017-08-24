.. raw:: html
   
   <p align="center">
      <img src="logo.png">
   </p>

=========
studio.ml
=========

`Github <https://github.com/pypa/pip>`_ |
`pip <https://pypi.org/project/studioml/>`_ |


Studio is a model management framework written in Python to help simplify and expedite your model building experience. It was developed to minimize any overhead involved with the scheduling, running, monitoring or management of artifacts of your machine learning experiments in Python without invasion of your code. No one wants to spend their time configuring different machines, setting up dependencies, or playing archeology to track down previous model artifacts.

Most of the features are compatible with any Python machine learning framework (Keras, TensorFlow, scikit-learn, etc); some extra features are available for Keras and TensorFlow.

Most of the features are compatible with any Python machine learning framework (`Keras <https://github.com/fchollet/keras>`__, `TensorFlow <https://github.com/tensorflow/tensorflow>`__, `scikit-learn <https://github.com/scikit-learn/scikit-learn>`__, etc); some extra features are available for Keras and TensorFlow.

**Use Studio to:**

-  Capture experiment information- Python environment, files, dependencies and logs- without modifying the experiment code. Monitor and organize experiments using a web dashboard that integrates with TensorBoard.
-  Run experiments locally, remotely, or in the cloud (Google Cloud or Amazon EC2)
-   Manage artifacts
-   Perform hyperparameter search
-   Create customizable Python environments for remote workers.


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Introduction

   Home <README>

.. toctree::
   :hidden:
   :caption: Main Features

   artifacts

.. toctree::
   :hidden:
   :caption: Main Documentation

   cloud
   customenv
   ec2_setup
   gcloud_setup
   hyperparams
   model_pipelines
   remote_worker
   setup_database

