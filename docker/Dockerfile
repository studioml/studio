FROM nvidia/cuda:8.0-cudnn5-runtime-ubuntu14.04

RUN apt-get update && \
    apt-get -y install python-pip git && \
    sudo pip install --upgrade pip && \
    sudo pip install tensorflow tensorflow-gpu keras
    

