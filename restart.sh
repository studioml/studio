#!/bin/bash

docker_cmd=nvidia-docker
docker_img=tfstudio/base:0.0
eval nvidia-smi
if [ $? != 0 ]; then
    docker_cmd=docker
fi

: "${GOOGLE_APPLICATION_CREDENTIALS?Need to point GOOGLE_APPLICATION_CREDENTIALS to the google credentials file}"

gac_path=${
repo="https://github.com/ilblackdragon/studio"
branch="queueing"

$docker 
$docker_cmd run --rm -it \
            -v $HOME/.tfstudio:/root/home $docker_img \
            -v $GOOGLE_APPLICATION_CREDENTIALS
        /bin/bash -c \
            "git clone $repo && \
            cd studio && \
            git checkout $branch && \
            sudo pip install --upgrade pip && \
            sudo pip install -e . --upgrade && \
            mkdir /workspace && cd /workspace && \
            studio-lworker"

