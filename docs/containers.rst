=========================
Containerized experiments
=========================

Some experiments may require more than just a specific python environment to be run reproducibly. For instance, 2017 NIPS running 
competition relied on a specific set of system-level pacakges for walker physics simulations. To address such experiments, Studio.ML
supports execution in containers by using Singularity (https://singularity.lbl.gov). Singularity supports both Docker and its own format 
of containers. Containers can be used in two main ways:

1. Running experiment using container environment
-------------------------------------------------
In this mode, an environment is set up within the container, but the python code is outside. Studio.ML with help of Singularity 
mounts copy of current directory and artifacts into the container and executes the script. Typical command line will look like

::
    
    studio run --container=/path/to/container.simg script.py args


Note that if your script is using Studio.ML library functions (such as `fs_tracker.get_artifact()`), Studio.ML will need to be
installed within the container. 

2. Running experiment using executable container
------------------------------------------------
Both singularity and docker support executable containers. Studio.ML experiment can consist solely out of an executable container:

::

    studio run --container=/path/to/container.simg

In this case, the code does not even need to be python, but all Studio.ML perks (such as cloud execution with hardware selection,
keeping track of inputs and outputs of the experiment etc) still apply. There is even an artifact management - artifacts will be
seen in the container in the folder one level up from working directory. 

Containers can be located either locally as `*.simg` files, or in the Singularity/Docker hub. In the latter case, provide a link that 
starts with `shub://` or `dockerhub://`




