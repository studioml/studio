#!/usr/bin/env python
import os
import time

import googleapiclient.discovery
import uuid
import math
import json

from . import git_util, logs
from .gpu_util import memstr2int
from .cloud_worker_util import insert_user_startup_script


class GCloudWorkerManager(object):
    def __init__(self, zone='us-east1-c',
                 auth_cookie=None, verbose=10, branch=None,
                 user_startup_script=None):
        assert 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys()
        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
            credentials_dict = json.loads(f.read())

        self.compute = googleapiclient.discovery.build('compute', 'v1')

        self.startup_script_file = os.path.join(
            os.path.dirname(__file__),
            'scripts/gcloud_worker_startup.sh')

        self.install_studio_script = os.path.join(
            os.path.dirname(__file__),
            'scripts/install_studio.sh')

        self.zone = zone
        self.projectid = credentials_dict['project_id']
        self.logger = logs.getLogger("GCloudWorkerManager")
        self.logger.setLevel(verbose)
        self.auth_cookie = auth_cookie
        self.user_startup_script = user_startup_script
        self.repo_url = git_util.get_my_repo_url()
        self.branch = branch if branch else git_util.get_my_checkout_target()
        self.log_bucket = "studioml-logs"

        if user_startup_script:
            self.logger.warn('User startup script argument is deprecated')

    def start_worker(
            self,
            queue_name,
            resources_needed={},
            blocking=False,
            ssh_keypair=None,
            timeout=300,
            ports=[]):

        if ssh_keypair is not None:
            self.logger.warn('ssh keypairs are not supported ' +
                             'for google workers')

        if resources_needed is None:
            resources_needed = {}

        name = self._generate_instance_name()

        config = self._get_instance_config(
            resources_needed, queue_name, timeout=timeout)

        config['name'] = name

        op = self.compute.instances().insert(
            project=self.projectid,
            zone=self.zone,
            body=config).execute()

        if blocking:
            self._wait_for_operation(op['name'])
            self.logger.debug('worker {} created'.format(name))
            return name
        else:
            return (name, op['name'])

    def start_spot_workers(
            self,
            queue_name,
            bid=None,
            resources_needed={},
            ssh_keypair=None,
            queue_upscaling=True,
            start_workers=1,
            max_workers=100,
            timeout=300,
            ports=[]):

        if resources_needed is None:
            resources_needed = {}

        if queue_upscaling is not False:
            self.logger.warn("autoscaling on the queue is not " +
                             "supported for google workers yet")

        if ssh_keypair is not None:
            self.logger.warn('ssh keypairs are not supported ' +
                             'for google workers')

        if bid is not None:
            self.logger.warn("bidding is not supported for " +
                             "google spot instances")

        template_name = self._generate_template_name()
        group_name = self._generate_group_name()

        config = self._get_instance_config(
            resources_needed, queue_name, timeout=timeout)
        config['scheduling']['preemptible'] = True
        config['machineType'] = config['machineType'].split('/')[-1]
        config['metadata']['items'].append(
            {'key': 'groupname', 'value': group_name})

        template_config = {
            'name': template_name,
            'properties': config
        }

        op = self.compute.instanceTemplates() \
            .insert(project=self.projectid, body=template_config) \
            .execute()

        self._wait_for_operation(op['name'], 'global')

        self.logger.info('instance template {} added'.format(template_name))

        self.compute.instanceGroupManagers() .insert(
            project=self.projectid,
            zone=self.zone,
            body={
                "baseInstanceName": self._generate_instance_name(),
                "instanceTemplate": 'global/instanceTemplates/' +
                template_name,
                "name": group_name,
                "targetSize": start_workers}) .execute()

        self.logger.info('Managed groupd {} created'.format(group_name))

    def _get_instance_config(self, resources_needed, queue_name, timeout=300):
        # image_response = self.compute.images().getFromFamily(
        #    project='studio-ed756', family='studioml').execute()

        image_response = None

        if image_response is None:
            image_response = self.compute.images().getFromFamily(
                project='ubuntu-os-cloud', family='ubuntu-1604-lts').execute()

        source_disk_image = image_response['selfLink']

        # Configure the machine
        machine_type = self._generate_machine_type(resources_needed)
        self.logger.debug('Machine type = {}'.format(machine_type))

        with open(self.startup_script_file, 'r') as f:
            startup_script = f.read()

        with open(self.install_studio_script) as f:
            install_studio_script = f.read()

        startup_script = insert_user_startup_script(
            self.user_startup_script,
            startup_script, self.logger)

        startup_script = startup_script.replace(
            '{install_studio}', install_studio_script)
        startup_script = startup_script.format(
            studioml_branch=self.branch,
            repo_url=self.repo_url,
            log_bucket=self.log_bucket,
            use_gpus=resources_needed.get('gpus', 0)
        )

        self.logger.info('Startup script:')
        self.logger.info(startup_script)

        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
            credentials = f.read()

        if self.auth_cookie is not None:
            auth_key = os.path.basename(self.auth_cookie)
            with open(self.auth_cookie, 'r') as f:
                auth_data = f.read()
        else:
            auth_key = None
            auth_data = None

        config = {
            'machineType': machine_type,

            # Specify the boot disk and the image to use as a source.
            'disks': [
                {
                    'boot': True,
                    'autoDelete': True,
                    'initializeParams': {
                        'sourceImage': source_disk_image,
                    }
                }
            ],

            # Specify a network interface with NAT to access the public
            # internet.
            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],

            # Allow the instance to access cloud storage and logs.
            'serviceAccounts': [{
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/cloud-platform',
                ]
            }],

            # Metadata is readable from the instance and allows you to
            # pass configuration from deployment scripts to instances.
            'metadata': {
                'items': [{
                    'key': 'startup-script',
                    'value': startup_script
                }, {
                    'key': 'credentials',
                    'value': credentials
                }, {
                    'key': 'queue_name',
                    'value': queue_name
                }, {
                    'key': 'auth_key',
                    'value': auth_key
                }, {
                    'key': 'auth_data',
                    'value': auth_data
                }, {
                    'key': 'timeout',
                    'value': str(timeout)
                }]
            },
            "scheduling": {
                "preemptilble": False
            }
        }

        if 'hdd' in resources_needed.keys():
            config['disks'][0]['initializeParams']['diskSizeGb'] = \
                memstr2int(resources_needed['hdd']) / memstr2int('1Gb')

        if resources_needed['gpus'] > 0:
            gpu_type = "nvidia-tesla-k80"
            config['guestAccelerators'] = [
                {
                    "acceleratorType":
                        "projects/{}/zones/{}/acceleratorTypes/{}"
                        .format(self.projectid, self.zone, gpu_type),
                    "acceleratorCount": resources_needed['gpus']
                }
            ]

            config["scheduling"]['onHostMaintenance'] = "TERMINATE"
            config["automaticRestart"] = True

        return config

    def _stop_worker(self, worker_id, blocking=True):
        op = self.compute.instances().delete(
            project=self.projectid,
            zone=self.zone,
            instance=worker_id).execute()

        if blocking:
            self._wait_for_operation(op['name'])
        else:
            return op['name']

    def _generate_instance_name(self):
        return "worker-" + str(uuid.uuid4())

    def _generate_group_name(self):
        return "group-" + str(uuid.uuid4())

    def _generate_template_name(self):
        return "template-" + str(uuid.uuid4())

    def _generate_machine_type(self, resources_needed={}):
        if not any(resources_needed):
            machine_type = "zones/{}/machineTypes/n1-standard-1".format(
                self.zone)
        else:
            cpus = int(resources_needed['cpus'])
            default_ram_per_cpu = 4096
            ram = default_ram_per_cpu * cpus

            if 'ram' in resources_needed.keys():
                ram = memstr2int(resources_needed['ram']) / memstr2int('1Mb')
                ram = int(math.ceil(ram / 256.0) * 256)

            ram_per_cpu = ram / cpus
            assert 1024 <= ram_per_cpu and ram_per_cpu <= 6192, \
                "RAM per cpu should be between 0.9 and 6.5 Gb"

            machine_type = "zones/{}/machineTypes/custom-{}-{}".format(
                self.zone, cpus, ram)

        return machine_type

    def _wait_for_operation(self, operation, locality='zone'):
        self.logger.debug('Waiting for operation {} to finish...'.
                          format(operation))
        while True:
            if locality == 'zone':
                result = self.compute.zoneOperations().get(
                    project=self.projectid,
                    zone=self.zone,
                    operation=operation).execute()
            elif locality == 'global':
                result = self.compute.globalOperations().get(
                    project=self.projectid,
                    operation=operation).execute()
            else:
                raise ValueError(('Unknown locality {} ' +
                                  'should be zone or global'.format(locality)))

            if result['status'] == 'DONE':
                self.logger.debug("done.")
                if 'error' in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)
