FROM nvidia/cuda:8.0-cudnn6-devel-ubuntu16.04

# add tensorflow-gpu to use with gpu to sudo pip install 
# to use on linux machines with gpus
RUN apt-get update && \
    apt-get -y install python-pip python-dev python3-pip python3-dev python3 git wget && \
    python -m pip install --upgrade pip && \
    python3 -m pip install --upgrade pip    

COPY . /studio
RUN cd studio && \
    python -m pip install -e . --upgrade && \
    python3 -m pip install -e . --upgrade 
    


    

