import unittest
import yaml
import uuid
import os
import time
import tempfile
import shutil
import requests
import subprocess
import boto3

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from studio import model
from studio.auth import remove_all_keys

from studio.artifacts.artifact import Artifact
from studio.gcloud_artifact_store import GCloudArtifactStore
from studio.storage.storage_handler import StorageHandler
from studio.extra_util import has_aws_credentials
from env_detect import on_gcp, on_aws

def _get_config():
    config_name = "test_config.yaml"
    config_file = os.path.join(
        os.path.dirname(
            os.path.realpath(__file__)),
        config_name)
    with open(config_file) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    return config

def _get_provider():
    config = _get_config()
    return model.get_db_provider(config)

def _build(art_dict) -> Artifact:
    art = Artifact("artifact", art_dict)
    return art

class ArtifactStoreTest(object):
    _multiprocess_shared_ = True

    def get_store(self, config_name='test_config.yaml'):
        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        with open(config_file) as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)

        return model.get_db_provider(config).storage_handler

    def test_get_put_artifact(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        random_str = str(uuid.uuid4())

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))

        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', str(uuid.uuid4()) + '.txt')
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact = _build({'key': 'tests/' + str(uuid.uuid4()) + '.tar'})
        fb.put_artifact(artifact, tmp_dir)
        shutil.rmtree(tmp_dir)
        fb.get_artifact(artifact, tmp_dir)

        with open(tmp_filename, 'r') as f:
            line = f.read()

        shutil.rmtree(tmp_dir)
        self.assertTrue(line == random_str)
        fb.delete_artifact(artifact)

    @unittest.skip('sometimes fails in travis at time assertion' +
                   ', peterz figure out')
    def test_get_put_cache(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        strlen = 10000000
        random_str = str(os.urandom(strlen))

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', str(uuid.uuid4()) + '.txt')

        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact = _build({'key': 'tests/' + str(uuid.uuid4()) + '.tgz'})

        fb.put_artifact(artifact, tmp_dir)
        shutil.rmtree(tmp_dir)

        tic1 = time.clock()
        fb.get_artifact(artifact, tmp_dir)
        os.utime(tmp_dir, None)
        tic2 = time.clock()
        fb.get_artifact(artifact, tmp_dir)
        tic3 = time.clock()

        with open(tmp_filename, 'r') as f:
            line = f.read()

        shutil.rmtree(tmp_dir)
        self.assertTrue(line == random_str)

        self.assertTrue(tic3 - tic2 < (tic2 - tic1))
        fb.delete_artifact(artifact)

    def test_get_artifact_url(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact_key = 'tests/test_' + str(uuid.uuid4())
        artifact = _build({'key': artifact_key})
        fb.put_artifact(artifact, tmp_filename)
        url = fb.get_artifact_url(artifact)
        os.remove(tmp_filename)
        response = requests.get(url)
        self.assertEqual(response.status_code, 200)
        tar_filename = os.path.join(tempfile.gettempdir(),
                                    str(uuid.uuid4()) + '.tgz')
        with open(tar_filename, 'wb') as f:
            f.write(response.content)

        ptar = subprocess.Popen(['tar', '-xf', tar_filename],
                                cwd=tempfile.gettempdir())

        tarout, _ = ptar.communicate()

        with open(tmp_filename, 'r') as f:
            self.assertEqual(f.read(), random_str)

        os.remove(tmp_filename)
        os.remove(tar_filename)
        fb.delete_artifact(artifact)

    def test_delete_file(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        random_str = str(uuid.uuid4())

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', str(uuid.uuid4()) + '.txt')
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact_key = 'tests/test_' + str(uuid.uuid4())
        artifact = _build({'key': artifact_key})
        fb.put_artifact(artifact, tmp_filename)
        shutil.rmtree(tmp_dir)
        fb.delete_artifact(artifact)
        fb.get_artifact(artifact, tmp_dir)

        exception_raised = False
        try:
            with open(tmp_filename, 'r') as f:
                f.read()
        except IOError:
            exception_raised = True

        self.assertTrue(exception_raised)

    def test_get_qualified_location(self):
        fb = self.get_store()
        key = str(uuid.uuid4())
        qualified_location = fb.get_qualified_location(key)
        expected_qualified_location = self.get_qualified_location_prefix() + \
            key

        self.assertEqual(qualified_location, expected_qualified_location)

@unittest.skipIf(
    not on_gcp(),
    'User indicated not on gcp')
class FirebaseArtifactStoreTest(ArtifactStoreTest, unittest.TestCase):
    # Tests of private methods

    def get_qualified_location_prefix(self):
        return "gs://studio-ed756.appspot.com/"

    def test_get_file_url(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')

        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'wt') as f:
            f.write(random_str)

        key = 'tests/' + str(uuid.uuid4()) + '.txt'
        fb._upload_file(key, tmp_filename)

        url = fb._get_file_url(key)
        response = requests.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('utf-8'),
                          random_str)
        fb._delete_file(key)
        os.remove(tmp_filename)

    def test_get_file_url_auth(self):
        remove_all_keys()
        fb = self.get_store('test_config_auth.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        key = 'authtest/' + str(uuid.uuid4()) + '.txt'
        fb._upload_file(key, tmp_filename)

        url = fb._get_file_url(key)
        response = requests.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('utf-8'),
                          random_str)
        fb._delete_file(key)
        os.remove(tmp_filename)

    def test_upload_download_file_noauth(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        key = 'authtest/' + str(uuid.uuid4()) + '.txt'
        fb._upload_file(key, tmp_filename)
        os.remove(tmp_filename)
        fb._download_file(key, tmp_filename)

        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file_bad(self):
        # smoke test to make sure attempt to access a wrong file
        # in the database is wrapped and does not crash the system
        fb = self.get_store('test_bad_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('tests/test_upload_download.txt', tmp_filename)
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)

    def test_upload_download_file_auth(self):
        remove_all_keys()
        fb = self.get_store('test_config_auth.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        key = 'authtest/' + str(uuid.uuid4())
        fb._upload_file(key, tmp_filename)
        os.remove(tmp_filename)

        # test an authorized attempt to delete file
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        fb._delete_file(key)
        remove_all_keys()
        fb = self.get_store('test_config_auth.yaml')
        # to make sure file is intact and the same as we uploaded

        fb._download_file(key, tmp_filename)

        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file(key)
        fb._download_file(key, tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file(self):
        fb = self.get_store()
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            str(uuid.uuid4()) + '.txt')

        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        key = 'tests/' + str(uuid.uuid4()) + '.txt'
        fb._upload_file(key, tmp_filename)
        os.remove(tmp_filename)
        fb._download_file(key, tmp_filename)
        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file(key)
        fb._download_file(key, tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))

@unittest.skipIf(
    not on_gcp(),
    'User indicated not on gcp')
class UserIndicatedOnGCPTest(unittest.TestCase):
    def test_on_enviornment(self):
        self.assertTrue('GOOGLE_APPLICATION_CREDENTIALS' in os.environ.keys())


@unittest.skipIf(
    (not on_gcp()) or
    'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
    'Skipping due to userinput or GCP Not detected')
class GCloudArtifactStoreTest(ArtifactStoreTest, unittest.TestCase):

    def get_store(self, config_name=None):
        store = ArtifactStoreTest.get_store(
            self, 'test_config_gcloud_storage.yaml')
        self.assertTrue(isinstance(store, GCloudArtifactStore))
        return store

    def get_qualified_location_prefix(self):
        store = self.get_store()
        return "gs://" + store.get_bucket() + "/"


@unittest.skipIf(
    not on_aws(),
    'User indicated not on aws')
class UserIndicatedOnAWSTest(unittest.TestCase):
    def test_on_enviornment(self):
        self.assertTrue(has_aws_credentials())


@unittest.skipIf(
     _get_provider() and not has_aws_credentials(),
    'Skipping due to userinput or AWS Not detected')
class S3ArtifactStoreTest(ArtifactStoreTest, unittest.TestCase):

    def get_store(self, config_name=None):
        store = ArtifactStoreTest.get_store(
            self, 'test_config.yaml')
        self.assertTrue(isinstance(store, StorageHandler))
        return store

    def get_qualified_location_prefix(self):
        store = self.get_store()
        return store.get_qualified_location("")


if __name__ == "__main__":
    unittest.main()
