FROM nvidia/cuda:8.0-cudnn6-devel-ubuntu16.04

# add tensorflow-gpu to use with gpu to sudo pip install 
# to use on linux machines with gpus
RUN apt-get update && \
    apt-get -y install python-pip python-dev git wget && \
    pip install --upgrade pip && \
    pip install tensorflow tensorflow-gpu 

COPY . /studio
RUN cd studio && \
    pip install -e . --upgrade

    

