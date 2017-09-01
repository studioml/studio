=========
Studio.ml
=========

`Github <https://github.com/pypa/pip>`_ |
`pip <https://pypi.org/project/studioml/>`_ |


Studio is a model management framework written in Python to help simplify and expedite your model building experience. It was developed to minimize the overhead involved with scheduling, running, monitoring and managing artifacts of your machine learning experiments. No one wants to spend their time configuring different machines, setting up dependencies, or playing archeologist to track down previous model artifacts.

Most of the features are compatible with any Python machine learning framework (`Keras <https://github.com/fchollet/keras>`__, `TensorFlow <https://github.com/tensorflow/tensorflow>`__, `PyTorch <https://github.com/pytorch/pytorch>`__, `scikit-learn <https://github.com/scikit-learn/scikit-learn>`__, etc) without invasion of your code; some extra features are available for Keras and TensorFlow.

**Use Studio to:**

-  Capture experiment information- Python environment, files, dependencies and logs- without modifying the experiment code. Monitor and organize experiments using a web dashboard that integrates with TensorBoard.
-  Run experiments locally, remotely, or in the cloud (Google Cloud or Amazon EC2)
-   Manage artifacts
-   Perform hyperparameter search
-   Create customizable Python environments for remote workers.


.. toctree::
   :hidden:
   :caption: Introduction

   Getting Started  <README>
   installation
   authentication
   cli

.. toctree::
   :hidden:
   :caption: Main Documentation

   artifacts
   hyperparams
   model_pipelines
   setup_database

.. toctree::
   :hidden:
   :caption: Remote computing

   remote_worker
   customenv

.. toctree::
   :hidden:
   :caption: Cloud computing

   cloud
   ec2_setup
   gcloud_setup

