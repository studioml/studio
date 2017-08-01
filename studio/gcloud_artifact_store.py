import os
import uuid

import logging
import time
import calendar
import tempfile
import re
from threading import Thread
import subprocess
import requests
import certifi
import json
import shutil

from google.cloud import storage
import fs_tracker
import util


logging.basicConfig()


class GCloudArtifactStore():
    def __init__(config, verbose=10):
        self.logger = logging.getLogger('GCloudArtifactStore')
        self.logger.setLevel(verbose)
        self.client = storage.Client()

        self.basebucket = config['bucket']

    def put_artifact(
            self,
            artifact,
            local_path=None,
            cache=True,
            background=False):
        raise NotImplementedError


    def get_artifact(
            self,
            artifact,
            local_path=None,
            only_newer=True,
            background=False):
        raise NotImplementedError

    def get_artifact_url(self, artifact):
        if 'key' in artifact.keys():
            return self._get_file_url(artifact['key'])
        return None

    def delete_artifact(self, artifact):
        if 'key' in artifact.keys():
            self._delete_file(artifact['key'])

    def _get_file_url(self, filename):
        pass




    

