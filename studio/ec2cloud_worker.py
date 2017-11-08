try:
    import boto3
except BaseException:
    boto3 = None

import uuid
import logging
import os
import base64
import requests
import json
import six

from . import git_util
from .gpu_util import memstr2int
from .cloud_worker_util import insert_user_startup_script

logging.basicConfig()

# list of instance types sorted by price
_instance_specs = {
    'c4.large': {
        'cpus': 2,
        'ram': '3.75g',
        'gpus': 0
    },

    'c4.xlarge': {
        'cpus': 4,
        'ram': '7.5g',
        'gpus': 0
    },
    'c4.2xlarge': {
        'cpus': 8,
        'ram': '15g',
        'gpus': 0
    },
    'c4.4xlarge': {
        'cpus': 16,
        'ram': '30g',
        'gpus': 0
    },
    'p2.xlarge': {
        'cpus': 4,
        'ram': '61g',
        'gpus': 1
    },
    'c4.8xlarge': {
        'cpus': 36,
        'ram': '60g',
        'gpus': 0
    },
    'p2.8xlarge': {
        'cpus': 32,
        'ram': '488g',
        'gpus': 8
    },
    'p2.16xlarge': {
        'cpus': 64,
        'ram': '732g',
        'gpus': 16
    }
}


class EC2WorkerManager(object):

    def __init__(self, auth_cookie=None, verbose=10, branch=None,
                 user_startup_script=None):
        self.startup_script_file = os.path.join(
            os.path.dirname(__file__),
            'scripts/ec2_worker_startup.sh')

        self.install_studio_script = os.path.join(
            os.path.dirname(__file__),
            'scripts/install_studio.sh')

        self.client = boto3.client('ec2')
        self.asclient = boto3.client('autoscaling')
        self.cwclient = boto3.client('cloudwatch')

        self.region = self.client._client_config.region_name

        self.logger = logging.getLogger('EC2WorkerManager')
        self.logger.setLevel(verbose)
        self.auth_cookie = auth_cookie

        self.prices = self._get_ondemand_prices(_instance_specs.keys())

        self.repo_url = git_util.get_my_repo_url()
        self.branch = branch if branch else git_util.get_my_checkout_target()
        self.user_startup_script = user_startup_script

        if user_startup_script:
            self.logger.warn('User startup script argument is deprecated')

    def _get_image_id(self):
        # return 'ami-cd0f5cb6'  # vanilla ubuntu 16.04 image
        return 'ami-a9a47cd3'  # studio.ml gpu image with python2 and python3

    def _get_block_device_mappings(self, resources_needed):
        return [{
            'DeviceName': '/dev/sda1',
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': int(memstr2int(resources_needed['hdd']) /
                                  memstr2int('1g')),
                'VolumeType': 'standard'
            }
        }]

    def start_worker(
            self,
            queue_name,
            resources_needed={},
            blocking=True,
            ssh_keypair=None,
            timeout=300):

        imageid = self._get_image_id()

        name = self._generate_instance_name()

        instance_type = self._select_instance_type(resources_needed)

        startup_script = self._get_startup_script(
            resources_needed, queue_name, timeout=timeout)

        if ssh_keypair is not None:
            groupid = self._create_security_group(ssh_keypair)

        self.logger.info(
            'Starting EC2 instance of type {}'.format(instance_type))
        kwargs = {
            'BlockDeviceMappings':
                self._get_block_device_mappings(resources_needed),
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
            'Starting instance {}'.format(
                response['Instances'][0]['InstanceId']))

    def _select_instance_type(self, resources_needed):
        sorted_specs = sorted(_instance_specs.items(),
                              key=lambda x: self.prices[x[0]])
        for instance in sorted_specs:
            if int(
                instance[1]['cpus']) >= int(
                resources_needed['cpus']) and memstr2int(
                instance[1]['ram']) >= memstr2int(
                resources_needed['ram']) and int(
                    instance[1]['gpus']) >= int(
                        resources_needed['gpus']):
                return instance[0]

        raise ValueError('No instances that satisfy requirements {} '
                         'can be found'.format(resources_needed))

    def _get_startup_script(
            self,
            resources_needed,
            queue_name,
            autoscaling_group=None,
            timeout=300):
        if self.auth_cookie is not None:
            auth_key = os.path.basename(self.auth_cookie)
            with open(self.auth_cookie, 'r') as f:
                auth_data = f.read()
        else:
            auth_key = None
            auth_data = None

        credentials = ''

        if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys():
            with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
                credentials = f.read()
        else:
            self.logger.info('credentials NOT found')

        with open(self.startup_script_file) as f:
            startup_script = f.read()

        with open(self.install_studio_script) as f:
            install_studio_script = f.read()

        startup_script = startup_script.replace(
            '{install_studio}', install_studio_script)

        startup_script = startup_script.format(
            auth_key=auth_key if auth_key else "",
            queue_name=queue_name,
            auth_data=base64.b64encode(auth_data.encode('utf-8'))
            .decode('utf-8') if auth_data else "",
            google_app_credentials=base64.b64encode(
                credentials.encode('utf-8')).decode('utf-8'),
            aws_access_key=self.client._request_signer._credentials.access_key,
            aws_secret_key=self.client._request_signer._credentials.secret_key,
            autoscaling_group=autoscaling_group if autoscaling_group else "",
            region=self.region,
            use_gpus=0 if resources_needed['gpus'] == 0 else 1,
            timeout=timeout,
            repo_url=self.repo_url,
            studioml_branch=self.branch,
        )

        startup_script = insert_user_startup_script(
            self.user_startup_script,
            startup_script, self.logger)

        self.logger.info('Startup script:')
        self.logger.info(startup_script)

        return startup_script

    def _generate_instance_name(self):
        return 'studioml_worker_' + str(uuid.uuid4())

    def _create_security_group(self, ssh_keypair):
        group_name = str(uuid.uuid4())

        response = self.client.create_security_group(
            GroupName=group_name,
            Description='group to provide ssh access to studioml workers')
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
        return groupid

    def start_spot_workers(
            self,
            queue_name,
            bid_price,
            resources_needed={},
            ssh_keypair=None,
            queue_upscaling=True,
            start_workers=1,
            max_workers=100,
            timeout=300):

        # TODO should be able to put bid price as None,
        # which means price of on-demand instance
        # or maybe specify bid_price as a fraction of on-demand price

        instance_type = self._select_instance_type(resources_needed)

        asg_name = "studioml-" + str(uuid.uuid4())
        launch_config_name = asg_name + "_launch_config"

        startup_script = self._get_startup_script(
            resources_needed, queue_name, asg_name, timeout=timeout)

        if bid_price.endswith('%'):
            bid_price = str(self.prices[instance_type] *
                            float(bid_price.replace('%', '')) / 100)

        self.logger.info('Price bid for instance type {} : {}'
                         .format(instance_type, bid_price))

        launch_config = {
            "ImageId": self._get_image_id(),
            "UserData": startup_script,
            "InstanceType": instance_type,
            "BlockDeviceMappings": self._get_block_device_mappings(
                resources_needed),
            "InstanceMonitoring": {
                'Enabled': False},
            "SpotPrice": bid_price,
        }

        if ssh_keypair is not None:
            groupid = self._create_security_group(ssh_keypair)
            launch_config['SecurityGroups'] = [groupid]
            launch_config['KeyName'] = ssh_keypair

        response = self.asclient.create_launch_configuration(
            LaunchConfigurationName=launch_config_name, **launch_config)

        self.logger.debug(
            "create_launch_configuration response:\n {}".format(response))

        asg_config = {
            "LaunchConfigurationName": asg_name + '_launch_config',
            "MinSize": 0,
            "MaxSize": max_workers,
            "DesiredCapacity": int(start_workers),
            "LoadBalancerNames": [],
            "AvailabilityZones": [self.region + "a"],
            "TerminationPolicies": ['NewestInstance'],
            "DefaultCooldown": 0,
            "NewInstancesProtectedFromScaleIn": True
        }

        self.logger.debug("Creating auto-scaling group " + asg_name)

        response = self.asclient.create_auto_scaling_group(
            AutoScalingGroupName=asg_name, **asg_config)

        if queue_upscaling:
            scaleup_policy_response = self.asclient.put_scaling_policy(
                AutoScalingGroupName=asg_name,
                PolicyName=asg_name + "_scaleup",
                AdjustmentType="ChangeInCapacity",
                ScalingAdjustment=1,
                Cooldown=0
            )

            self.cwclient.put_metric_alarm(
                AlarmName=asg_name + "_scaleup_alarm",
                MetricName="ApproximateNumberOfMessagesVisible",
                Namespace="AWS/SQS",
                Statistic="Average",
                Period=300,
                Threshold=1,
                ComparisonOperator="GreaterThanOrEqualToThreshold",
                EvaluationPeriods=1,
                AlarmActions=[scaleup_policy_response['PolicyARN']],
                Dimensions=[{
                    'Name': 'QueueName',
                    'Value': queue_name
                }]
            )

    def _get_ondemand_prices(self, instances=_instance_specs.keys()):

        # TODO un-hardcode the us-east as a region
        # so that prices are being read for a correct region

        price_path = os.path.join(os.path.expanduser('~'), '.studioml',
                                  'awsprices.json')
        try:
            self.logger.info('Reading AWS prices from cache...')
            with open(price_path, 'r') as f:
                offer_dict = json.load(f)

        except BaseException:
            self.logger.info(
                'Getting prices info from AWS (this may take a moment...)')

            r = requests.get(
                'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/' +
                'AmazonEC2/current/index.json')
            if r.status_code != 200:
                self.logger.error(
                    'Getting AWS offers returned code {}'.format(
                        r.status_code))

            offer_dict = r.json()
            with open(price_path, 'w') as f:
                f.write(json.dumps(offer_dict))

        self.logger.info('Done!')

        region_name = 'US East (N. Virginia)'

        prices = {}

        for instance_type in instances:
            product_sku = [
                k for k, v in six.iteritems(offer_dict['products'])
                if v['attributes'].get('instanceType') == instance_type and
                v['attributes']['tenancy'] == 'Shared' and
                v['attributes']['operatingSystem'] == 'Linux' and
                v['attributes']['location'] == region_name
            ]

            assert len(product_sku) == 1, \
                'Either no or too many products found for {}!' \
                .format(instance_type)

            prices[instance_type] = float(
                list(
                    list(
                        offer_dict['terms']['OnDemand']
                        [product_sku[0]].values()
                    )[0]['priceDimensions'].values()
                )[0]['pricePerUnit']['USD'])

        return prices
