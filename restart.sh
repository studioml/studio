#!/bin/bash

docker_cmd=nvidia-docker
docker_img=tfstudio/base:0.0

queue_name=$1

eval nvidia-smi
if [ $? != 0 ]; then
    docker_cmd=docker
fi

: "${GOOGLE_APPLICATION_CREDENTIALS?Need to point GOOGLE_APPLICATION_CREDENTIALS to the google credentials file}"

gac_path=${GOOGLE_APPLICATION_CREDENTIALS%/*}
gac_name=${GOOGLE_APPLICATION_CREDENTIALS##*/}
repo="https://github.com/ilblackdragon/studio"
branch="queueing2"

$docker 
$docker_cmd run --rm -it \
            -v $HOME/.tfstudio:/root/home $docker_img \
            -v $gac_path:/creds
            -e GOOGLE_APPLICATION_CREDENTIALS="/creds/$gac_name"
        /bin/bash -c \
            "git clone $repo && \
            cd studio && \
            git checkout $branch && \
            sudo pip install --upgrade pip && \
            sudo pip install -e . --upgrade && \
            mkdir /workspace && cd /workspace && \
            studio-lworker --queue=$queue_name"

