# Cloud computing for studio

TensorFlow studio can be configured to submit jobs to the cloud. Right now, only google cloud computing is supported (extenstion to EC2 is planned)
Specifically, once configured (see [here](gcloud_setup.md) for configuration instructions) command line

    studio-runner --cloud=gcloud my_script.py 

will create a new google compute engine instance, set up the python environment, run `my_script.py`, and shutdown the instance. You'll be able to see the progress of the job in studio ui.
Different experiments might require different hardware. Fortunately, google cloud offers flexibility of instance configuration; and TensorFlow Studio leverages that. 
To specify number of cpus or gpus needed, use flags --cpus and --gpus respectively. That is, command line:

    studio-runner --cloud=gcloud --cpus=8 --gpus=1 my_script.py 

will create an instance with 8 cpus and 1 gpu. The only available gpu in google cloud is Tesla K80 at the moment; we might provide some gpu selection flags in the future as well. 
The amount of ram and hard drive space can be configured via --ram / --hdd flags (using standard suffixes like g(G,Gb,GiB), m(M,MiB)). Note that the amount of RAM will be rounded up to a next factor of 256 Mb. Also note that for now extended RAM for google cloud is not supported, which means amount of RAM per CPU should be between 1 and 6 Gb.



