try:
    import boto3
except BaseException:
    boto3 = None

import uuid
import logging
import os
import base64

import hashlib
import pickle

from gpu_util import memstr2int


logging.basicConfig()

# list of instance types sorted by price
_instance_specs = [
    {
        'name': 'c4.large',
        'cpus': 2,
        'ram': '3.75g',
        'gpus': 0
    },
    {
        'name': 'c4.xlarge',
        'cpus': 4,
        'ram': '7.5g',
        'gpus': 0
    },
    {
        'name': 'c4.2xlarge',
        'cpus': 8,
        'ram': '15g',
        'gpus': 0
    },
    {
        'name': 'c4.4xlarge',
        'cpus': 16,
        'ram': '30g',
        'gpus': 0
    },
    {
        'name': 'p2.xlarge',
        'cpus': 4,
        'ram': '61g',
        'gpus': 1
    },
    {
        'name': 'c4.8xlarge',
        'cpus': 36,
        'ram': '60g',
        'gpus': 0
    },
    {
        'name': 'p2.8xlarge',
        'cpus': 32,
        'ram': '488g',
        'gpus': 8
    },
    {
        'name': 'p2.16xlarge',
        'cpus': 64,
        'ram': '732g',
        'gpus': 16
    }
]


class EC2WorkerManager(object):

    def __init__(self, auth_cookie=None):
        self.client = boto3.client('ec2')
        self.asclient = boto3.client('autoscaling')
        self.logger = logging.getLogger('EC2WorkerManager')
        self.logger.setLevel(10)
        self.auth_cookie = auth_cookie

    def _get_image_id(self):
        # vanilla ubuntu 14.04 image
        return 'ami-d15a75c7'

    def _get_block_device_mappings(self, resources_needed):
        return [{
            'DeviceName': '/dev/sdh',
            'Ebs': {
                'Encrypted': False,
                'DeleteOnTermination': True,
                'VolumeSize': memstr2int(resources_needed['hdd']) /
                memstr2int('1g'),
                'VolumeType': 'standard'
            }
        }]

    def start_worker(
            self,
            queue_name,
            resources_needed={},
            blocking=True,
            ssh_keypair=None):

        imageid = self._get_image_id()

        if self.auth_cookie is not None:
            auth_key = os.path.basename(self.auth_cookie)
            with open(self.auth_cookie, 'r') as f:
                auth_data = f.read()
        else:
            auth_key = None
            auth_data = None

        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
            credentials = f.read()

        name = self._generate_instance_name()

        instance_type, startup_script = self._select_instance_type(
            resources_needed)

        startup_script = startup_script.format(
            auth_key if auth_key else "",
            queue_name,
            base64.b64encode(auth_data) if auth_data else "",
            base64.b64encode(credentials)
        )

        self.logger.info('Startup script:')
        self.logger.info(startup_script)

        if ssh_keypair is not None:
            group_name = str(uuid.uuid4())

            response = self.client.create_security_group(
                GroupName=group_name,
                Description='Group to provide ssh access to workers')
            groupid = response['GroupId']

            response = self.client.authorize_security_group_ingress(
                GroupId=groupid,
                GroupName=group_name,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{
                        'CidrIp': '0.0.0.0/0'
                    }]
                }]
            )

        self.logger.info(
            'Starting EC2 instance of type {}'.format(instance_type))
        kwargs = {
            'BlockDeviceMappings': [{
                'DeviceName': '/dev/sdh',
                'VirtualName': 'ephemeral0',
                'Ebs': {
                    'Encrypted': False,
                    'DeleteOnTermination': True,
                    'VolumeSize': memstr2int(resources_needed['hdd']) /
                    memstr2int('1g'),
                    'VolumeType': 'standard'
                },
                'NoDevice': ''
            }],
            'ImageId': imageid,
            'InstanceType': instance_type,
            'MaxCount': 1,
            'MinCount': 1,
            'UserData': startup_script,
            'InstanceInitiatedShutdownBehavior': 'terminate',
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': name
                    },
                    {
                        'Key': 'Team',
                        'Value': 'tools'
                    }]
            }]
        }
        if ssh_keypair:
            kwargs['KeyName'] = ssh_keypair
            kwargs['SecurityGroupIds'] = [groupid]

        response = self.client.run_instances(**kwargs)
        self.logger.info(
            'Staring instance {}'.format(
                response['Instances'][0]['InstanceId']))

    def _select_instance_type(self, resources_needed):
        startup_script_filename = 'scripts/ec2_worker_startup.sh' \
            if int(resources_needed['gpus']) == 0 else \
            'scripts/ec2_gpuworker_startup.sh'

        with open(os.path.join(
                os.path.dirname(__file__),
                startup_script_filename),
                'r') as f:
            startup_script = f.read()

        for instance in _instance_specs:
            if int(
                instance['cpus']) >= int(
                resources_needed['cpus']) and memstr2int(
                instance['ram']) >= memstr2int(
                resources_needed['ram']) and int(
                    instance['gpus']) >= int(
                        resources_needed['gpus']):
                return instance['name'], startup_script

        raise ValueError('No instances that satisfy requirements {} '
                         'can be found'.format(resources_needed))

    def _generate_instance_name(self):
        return 'ec2worker_' + str(uuid.uuid4())

    def start_spot_workers(
            self,
            num_workers,
            bid_price,
            resources_needed={},
            ssh_keypair=None):

        # TODO should be able to put bid price as None,
        # which means price of on-demand instance
        # or maybe specify bid_price as a fraction of on-demand price

        instance_type, startup_script = self._select_instance_type(
            resources_needed)

        launch_config = {
            "ImageId": self._get_image_id(),
            "UserData": "",
            "InstanceType": instance_type,
            "BlockDeviceMappings": self._get_block_device_mappings(
                resources_needed),
            "InstanceMonitoring": {
                'Enabled': False},
            "SpotPrice": bid_price,
        }

        if ssh_keypair is not None:
            group_name = str(uuid.uuid4())

            response = self.client.create_security_group(
                GroupName=group_name,
                Description='Group to provide ssh access to workers')
            groupid = response['GroupId']

            response = self.client.authorize_security_group_ingress(
                GroupId=groupid,
                GroupName=group_name,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{
                        'CidrIp': '0.0.0.0/0'
                    }]
                }]
            )

            launch_config['SecurityGroups'] = [group_name]
            launch_config['KeyName'] = ssh_keypair

        launch_config_name = hashlib.sha256(
            pickle.dumps(launch_config)).hexdigest()

        existing_configs = self.asclient.describe_launch_configurations()

        if launch_config_name in [
                config['LaunchConfigurationName']
                for config in existing_configs['LaunchConfigurations']]:
            self.logger.debug(
                'Launch configuration {} exists'.format(launch_config_name))
        else:
            self.logger.debug(
                'Launch configuration {} does not exist, creating...'
                .format(launch_config_name))
            response = self.asclient.create_launch_configuration(
                LaunchConfigurationName=launch_config_name, **launch_config)

            self.logger.debug(
                "create_launch_configuration response:\n" + response)

        asg_config = {
            "LaunchConfigurationName": launch_config_name,
            "MinSize": 0,
            "MaxSize": num_workers,
            "DesiredCapacity": num_workers,
            "LoadBalancerNames": [],
            "AvailabilityZones": ['us-east-1d']
        }

        asg_name = hashlib.sha256(pickle.dumps(asg_config)).hexdigest()

        response = self.asclient.create_auto_scaling_group(
            AutoScalingGroupName=asg_name, **asg_config)

        print response
