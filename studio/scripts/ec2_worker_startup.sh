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


autoscaling_group="{autoscaling_group}"
instance_id=$(wget -q -O - http://169.254.169.254/latest/meta-data/instance-id)

echo "Environment varibles:"
env

{install_studio}

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
