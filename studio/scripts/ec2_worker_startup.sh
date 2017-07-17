#!/bin/bash

cd ~

mkdir -p .tfstudio/keys
key_name="{}"
queue_name="{}"
echo "{}" | base64 --decode > .tfstudio/keys/$key_name
echo "{}" | base64 --decode > /credentials.json

export GOOGLE_APPLICATION_CREDENTIALS=/credentials.json


code_url_base="https://storage.googleapis.com/studio-ed756.appspot.com/src"
code_ver="tfstudio-hyperparam_opt-2017-07-13_1.tgz"

sudo apt -y update 
sudo apt install -y wget python-pip git python-dev

wget $code_url_base/$code_ver 
tar -xzf $code_ver 
cd studio 
sudo pip install --upgrade pip 
sudo pip install -e . --upgrade 
mkdir /workspace && cd /workspace 
studio-remote-worker --queue=$queue_name 

# shutdown the instance
sudo shutdown now
