FROM nvidia/cuda:8.0-cudnn5-devel-ubuntu14.04

# add tensorflow-gpu to use with gpu to sudo pip install 
# to use on linux machines with gpus
RUN apt-get update && \
    apt-get -y install python-pip python-dev git wget && \
    sudo pip install --upgrade pip && \
    sudo pip install tensorflow && \
    wget "https://storage.googleapis.com/studio-ed756.appspot.com/src/tfstudio-artifacts-2017-06-23_4.tgz" && \
    tar -xzf tfstudio-artifacts-2017-06-23_4.tgz && \
    cd studio && \
    pip install -e . && \
    cd .. && rm -rf studio && rm tfstudio-artifacts-2017-06-23_4.tgz

    

