#!/bin/bash

cd ~

mkdir -p .tfstudio/keys
key_name="{}"
queue_name="{}"
echo "{}" | base64 --decode > .tfstudio/keys/$key_name
echo "{}" | base64 --decode > /credentials.json

export GOOGLE_APPLICATION_CREDENTIALS=/credentials.json


code_url_base="https://storage.googleapis.com/studio-ed756.appspot.com/src"
code_ver="tfstudio-ec2worker-2017-07-04_2.tgz"

cudnn="libcudnn5_5.1.10-1_cuda8.0_amd64.deb"

cuda_base="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1604/x86_64/"
cuda_ver="cuda-repo-ubuntu1604_8.0.61-1_amd64.deb"

sudo apt -y update 
sudo apt install -y wget python-pip git python-dev

# install cuda
wget $cuda_base/$cuda_ver
sudo dpkg -i $cuda_ver
sudo apt -y update
sudo apt install -y cuda

# install cudnn
wget $code_url_base/$cudnn
sudo dpkg -i $cudnn

wget $code_url_base/$code_ver 
tar -xzf $code_ver 
cd studio 
sudo pip install --upgrade pip 
sudo pip install tensorflow tensorflow-gpu
sudo pip install -e . --upgrade 

mkdir /workspace && cd /workspace 
studio-remote-worker --queue=$queue_name 

# shutdown the instance
sudo shutdown now
