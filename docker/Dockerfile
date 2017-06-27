FROM nvidia/cuda:8.0-cudnn5-devel-ubuntu14.04

# add tensorflow-gpu to use with gpu to sudo pip install 
# to use on linux machines with gpus
RUN apt-get update && \
    apt-get -y install python-pip git wget && \
    sudo pip install --upgrade pip && \
    sudo pip install tensorflow && \
    wget "https://storage.googleapis.com/studio-ed756.appspot.com/src/tfstudio-queueing2-2017-06-19_5.tgz" && \
    tar -xzf tfstudio-queueing2-2017-06-19_5.tgz && \
    cd studio && \
    pip install -e . && \
    cd .. && rm -rf studio && rm tfstudio-queueing2-2017-06-19_5.tgz

    

