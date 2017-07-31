#!/usr/bin/env python
import os
import time

import googleapiclient.discovery
import uuid
import logging
import math
import json

from gpu_util import memstr2int

logging.basicConfig()


class GCloudWorkerManager(object):
    def __init__(self, zone='us-central1-f', auth_cookie=None):
        assert 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys()
        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
            credentials_dict = json.loads(f.read())

        self.compute = googleapiclient.discovery.build('compute', 'v1')
        self.startup_script_file = os.path.join(
            os.path.dirname(__file__),
            'scripts/gcloud_worker_startup.sh')

        self.zone = zone
        self.projectid = credentials_dict['project_id']
        self.logger = logging.getLogger("GCloudWorkerManager")
        self.logger.setLevel(10)
        self.auth_cookie = auth_cookie

    def start_worker(
            self,
            queue_name,
            resources_needed={},
            blocking=True,
            ssh_keypair=None):
        assert ssh_keypair is None, \
            'ssh keypairs are not supported for google workers'
        if resources_needed is None:
            resources_needed = {}

        image_response = self.compute.images().getFromFamily(
            project='debian-cloud', family='debian-8').execute()
        source_disk_image = image_response['selfLink']

        # Configure the machine
        machine_type = self._generate_machine_type(resources_needed)
        self.logger.debug('Machine type = {}'.format(machine_type))
        with open(self.startup_script_file, 'r') as f:
            startup_script = f.read()

        with open(os.environ['GOOGLE_APPLICATION_CREDENTIALS'], 'r') as f:
            credentials = f.read()

        name = self._generate_instance_name()

        if self.auth_cookie is not None:
            auth_key = os.path.basename(self.auth_cookie)
            with open(self.auth_cookie, 'r') as f:
                auth_data = f.read()
        else:
            auth_key = None
            auth_data = None

        config = {
            'name': name,
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

            # Allow the instance to access cloud storage and logging.
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
                }]
            }
        }

        if 'hdd' in resources_needed.keys():
            config['disks'][0]['initializeParams']['diskSizeGb'] = \
                memstr2int(resources_needed['hdd']) / memstr2int('1Gb')

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

    def _wait_for_operation(self, operation):
        self.logger.debug('Waiting for operation {} to finish...'.
                          format(operation))
        while True:
            result = self.compute.zoneOperations().get(
                project=self.projectid,
                zone=self.zone,
                operation=operation).execute()

            if result['status'] == 'DONE':
                self.logger.debug("done.")
                if 'error' in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)
