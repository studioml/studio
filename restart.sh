#!/bin/bash

docker_cmd=nvidia-docker
docker_img=tfstudio/base:0.0
docker_img=19c1d33a5747

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

bash_cmd="git clone $repo && \
            cd studio && \
            git checkout $branch && \
            sudo pip install --upgrade pip && \
            sudo pip install -e . --upgrade && \
            mkdir /workspace && cd /workspace && \
            studio-rworker --queue=$queue_name"


echo $bash_cmd

$docker_cmd run --rm -it \
            -v $HOME/.tfstudio:/root/.tfstudio \
            -v $gac_path:/creds \
            -e GOOGLE_APPLICATION_CREDENTIALS="/creds/$gac_name" \
            $docker_img \
        /bin/bash -c "$bash_cmd"

