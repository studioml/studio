#!/bin/bash

cd ~
mkdir .aws
echo "[default]" > .aws/config
echo "region = {region}" >> .aws/config

mkdir -p .studioml/keys
key_name="{auth_key}"
queue_name="{queue_name}"
echo "{auth_data}" | base64 --decode > .studioml/keys/$key_name
echo "{google_app_credentials}" | base64 --decode > /credentials.json

export GOOGLE_APPLICATION_CREDENTIALS=/credentials.json

export AWS_ACCESS_KEY_ID="{aws_access_key}"
export AWS_SECRET_ACCESS_KEY="{aws_secret_key}"

code_url_base="https://storage.googleapis.com/studio-ed756.appspot.com/src"
code_ver="studioml-64_config_location-2017-08-04_1.tgz"

autoscaling_group="{autoscaling_group}"

echo "Environment varibles:"
env

sudo apt -y update 
sudo apt install -y wget python-pip git python-dev jq
sudo pip install --upgrade pip 
sudo pip install --upgrade awscli

wget $code_url_base/$code_ver 
tar -xzf $code_ver 
cd studio 

if [[ "{use_gpus}" -eq 1 ]]; then
    cudnn="libcudnn5_5.1.10-1_cuda8.0_amd64.deb"
    cuda_base="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1604/x86_64/"
    cuda_ver="cuda-repo-ubuntu1604_8.0.61-1_amd64.deb"

    # install cuda
    wget $cuda_base/$cuda_ver
    sudo dpkg -i $cuda_ver
    sudo apt -y update
    sudo apt install -y cuda

    # install cudnn
    wget $code_url_base/$cudnn
    sudo dpkg -i $cudnn
    sudo pip install tensorflow tensorflow-gpu
fi

sudo pip install -e . --upgrade 
mkdir /workspace && cd /workspace 
studio remote worker --queue=$queue_name  --verbose=debug --timeout=300

# shutdown the instance
echo "Work done"

if [ -n $autoscaling_group ]; then

    echo "Getting info for auto-scaling group $autoscaling_group"

    asg_info="aws autoscaling describe-auto-scaling-groups --auto-scaling-group-name $autoscaling_group"
    desired_size=$( $asg_info | jq --raw-output ".AutoScalingGroups | .[0] | .DesiredCapacity" )
    launch_config=$( $asg_info | jq --raw-output ".AutoScalingGroups | .[0] | .LaunchConfigurationName" )

    echo "Launch config: $launch_config"
    echo "Current autoscaling group size (desired): $desired_size"
        
    if [[ $desired_size -gt 1 ]]; then
        new_desired_size=$((desired_size - 1))
        echo "Decreasing ASG size to $new_desired_size"
        aws autoscaling update-auto-scaling-group --auto-scaling-group-name $autoscaling_group --desired-capacity $new_desired_size
    else
        echo "Deleting launch configuration and auto-scaling group"
        aws autoscaling delete-auto-scaling-group --auto-scaling-group-name $autoscaling_group --force-delete
        aws autoscaling delete-launch-configuration --launch-configuration-name $launch_config
    fi
    # if desired_size > 1 decrease desired size (with cooldown - so that it does not try to remove any other instances!)
    # else delete the group - that should to the shutdown 
    # 

fi
echo "Shutting the instance down!"
sudo shutdown now
