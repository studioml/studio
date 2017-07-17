#!/bin/bash


metadata_url="http://metadata.google.internal/computeMetadata/v1/instance"
queue_name=$(curl "${metadata_url}/attributes/queue_name" -H  "Metadata-Flavor: Google")
key_name=$(curl "${metadata_url}/attributes/auth_key" -H  "Metadata-Flavor: Google")

zone=$(curl "${metadata_url}/zone" -H  "Metadata-Flavor: Google")
instance_name=$(curl "${metadata_url}/name" -H  "Metadata-Flavor: Google")

cd ~

mkdir -p .tfstudio/keys
curl "${metadata_url}/attributes/auth_data" -H  "Metadata-Flavor: Google" > .tfstudio/keys/${key_name}
curl "${metadata_url}/attributes/credentials" -H  "Metadata-Flavor: Google" > /credentials.json
export GOOGLE_APPLICATION_CREDENTIALS=/credentials.json


: "${GOOGLE_APPLICATION_CREDENTIALS?Need to point GOOGLE_APPLICATION_CREDENTIALS to the google credentials file}"
: "${queue_name?Queue name is not specified (pass as a script argument}"

gac_path=${GOOGLE_APPLICATION_CREDENTIALS%/*}
gac_name=${GOOGLE_APPLICATION_CREDENTIALS##*/}
repo="https://github.com/ilblackdragon/studio"
branch="master"

#bash_cmd="git clone $repo && \
#            cd studio && \
#            git checkout $branch && \
#            sudo pip install --upgrade pip && \
#            sudo pip install -e . --upgrade && \
#            mkdir /workspace && cd /workspace && \
#            studio-rworker --queue=$queue_name"

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
studio-remote-worker --queue=$queue_name --verbose=debug

# shutdown the instance
gcloud compute instances delete $instance_name --zone $zone --quiet
