#!/bin/bash

exec > >(tee -i ~/ec2_worker_logfile.txt)
exec 2>&1

cd ~
mkdir .aws
echo "[default]" > .aws/config
echo "region = {region}" >> .aws/config

mkdir -p .studioml/keys
key_name="{auth_key}"
queue_name="{queue_name}"
echo "{auth_data}" | base64 --decode > .studioml/keys/$key_name
echo "{google_app_credentials}" | base64 --decode > credentials.json

export GOOGLE_APPLICATION_CREDENTIALS=~/credentials.json

export AWS_ACCESS_KEY_ID="{aws_access_key}"
export AWS_SECRET_ACCESS_KEY="{aws_secret_key}"

code_url_base="https://storage.googleapis.com/studio-ed756.appspot.com/src"
#code_ver="tfstudio-64_config_location-2017-08-04_1.tgz"

repo_url="{repo_url}"
branch="{studioml_branch}"


autoscaling_group="{autoscaling_group}"
instance_id=$(wget -q -O - http://169.254.169.254/latest/meta-data/instance-id)

echo "Environment varibles:"
env

if [ ! -d "studio" ]; then
    echo "Installing system packages..."
    #sudo add-apt-repository -y ppa:jonathonf/python-3.6
    sudo apt -y update
    sudo apt install -y wget git jq 
    #sudo apt install -y python python-pip python-dev python3.6 python3.6-dev python3-pip
    sudo apt install -y python python-pip python-dev python3 python3-dev python3-pip
    echo "python2 version: " $(python -V)

    sudo python -m pip install --upgrade pip
    sudo python -m pip install --upgrade awscli boto3

    #sudo ln -sf /usr/bin/python3.6 /usr/bin/python3
    #sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 2
    #sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.5 1
    #sudo update-alternatives --set python3 /usr/bin/python3.6

    echo "python3 version: " $(python3 -V)
   
    sudo python3 -m pip install --upgrade pip
    sudo python3 -m pip install --upgrade awscli boto3

    #wget $code_url_base/$code_ver
    #tar -xzf $code_ver
    #cd studio
    if [[ "{use_gpus}" -eq 1 ]]; then
        cudnn5="libcudnn5_5.1.10-1_cuda8.0_amd64.deb"
        cudnn6="libcudnn6_6.0.21-1_cuda8.0_amd64.deb"
        cuda_base="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1604/x86_64/"
        cuda_ver="cuda-repo-ubuntu1604_8.0.61-1_amd64.deb"

        # install cuda
        wget $cuda_base/$cuda_ver
        sudo dpkg -i $cuda_ver
        sudo apt -y update
        sudo apt install -y "cuda-8.0"

        # install cudnn
        wget $code_url_base/$cudnn5
        wget $code_url_base/$cudnn6
        sudo dpkg -i $cudnn5
        sudo dpkg -i $cudnn6

        sudo python  -m pip install tf-nightly tf-nightly-gpu --upgrade
        sudo python3 -m pip install tf-nightly tf-nightly-gpu --upgrade
    else
        sudo apt install -y default-jre
    fi
fi

if [[ "{use_gpus}" -ne 1 ]]; then
    rm -rf /usr/lib/x86_64-linux-gnu/libcuda*
fi

rm -rf studio
git clone $repo_url
if [[ $? -ne 0 ]]; then
    git clone https://github.com/studioml/studio
fi

cd studio
git pull
git checkout $branch
sudo python -m pip install -e . --upgrade
sudo python3 -m pip install -e . --upgrade

python $(which studio-remote-worker) --queue=$queue_name  --verbose=debug --timeout={timeout}

# sudo update-alternatives --set python3 

# shutdown the instance
echo "Work done"

hostname=$(hostname)
aws s3 cp /var/log/cloud-init-output.log "s3://studioml-logs/$queue_name/$hostname.txt"

if [[ -n $(who) ]]; then
    echo "Users are logged in, not shutting down"
    echo "Do not forget to shut the instance down manually"
    exit 0
fi



if [ -n $autoscaling_group ]; then

    echo "Getting info for auto-scaling group $autoscaling_group"

    asg_info="aws autoscaling describe-auto-scaling-groups --auto-scaling-group-name $autoscaling_group"
    desired_size=$( $asg_info | jq --raw-output ".AutoScalingGroups | .[0] | .DesiredCapacity" )
    launch_config=$( $asg_info | jq --raw-output ".AutoScalingGroups | .[0] | .LaunchConfigurationName" )

    echo "Launch config: $launch_config"
    echo "Current autoscaling group size (desired): $desired_size"

    if [[ $desired_size -gt 1 ]]; then
        echo "Detaching myself ($instance_id) from the ASG $autoscaling_group"
        aws autoscaling detach-instances --instance-ids $instance_id --auto-scaling-group-name $autoscaling_group --should-decrement-desired-capacity
        #new_desired_size=$((desired_size - 1))
        #echo "Decreasing ASG size to $new_desired_size"
        #aws autoscaling update-auto-scaling-group --auto-scaling-group-name $autoscaling_group --desired-capacity $new_desired_size
    else
        echo "Deleting launch configuration and auto-scaling group"
        aws autoscaling delete-auto-scaling-group --auto-scaling-group-name $autoscaling_group --force-delete
        aws autoscaling delete-launch-configuration --launch-configuration-name $launch_config
    fi
    # if desired_size > 1 decrease desired size (with cooldown - so that it does not try to remove any other instances!)
    # else delete the group - that should to the shutdown
    #

fi
aws s3 cp /var/log/cloud-init-output.log "s3://studioml-logs/$queue_name/$hostname.txt"
echo "Shutting the instance down!"
sudo shutdown now
