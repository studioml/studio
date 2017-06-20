# Artifact management

This page describes facilities that tfstudio provides for management of experiment artifacts. 
For now, artifact storage is backed by google cloud storage. 

## Basic usage
The idea behind artifact management is three-fold:
1. With no coding overhead capture the data that experiment depends on (e.g. dataset)
2. With minimal coding overhead save and visualize the results of the experiment (neural network weights, etc).
3. With minimal coding overhead make experiments reproducible on any machine (without manual data download, path correction etc).

Below we provide the examples of each use case. 

### Capture data 
Let's imagine that file `train_nn.py` in current directory trains neural network based on data located in `~/data/`. In order to capture the data, we need to invoke `studio-runner` as follows:

    studio-runner --arti=~/data:data train_nn.py

Flag `--arti` specifies that data at path ~/data needs to be captured once at the experiment startup. Additionally, tag `data` (provided as a value after `:`) allows script to access data
in a machine-independent way; and also distinguishes the dataset in the web-ui (Web UI page of the experiment will contain download link for tar-gzipped folder `~/data`)

### Save the result of the experiment 
Let's now consider an example of a python script that periodically saves some intermediate data (e.g. weigths of a neural network). The following example can be made more consise using 
keras or tensorflow built-in checkpointers, but we'll leave that as an exercise for the reader. 
Consider the following contents of file `train_linreg.py`:
    
    import numpy as np
    
    no_samples = 100
    dim_samples = 5

    X = np.random.random((no_samples, dim_samples))
    y = np.random.random((no_samples, 1))

    w = np.random.random((1, dim_samples))

    for 


## Default artifacts

## Mutable vs immutable artifacts

## Reusing artifacts from other experiment

## Under the hood
