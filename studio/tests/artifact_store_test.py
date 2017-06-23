import unittest
import yaml
import uuid
import os
import time
import tempfile
import shutil
import requests
import subprocess

from studio import model
from studio.auth import remove_all_keys


class ArtifactStoreTest(object):

    def get_store(self):
        return None

    def test_get_put_artifact(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        random_str = str(uuid.uuid4())

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', 'test_upload_download.txt')
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb.put_artifact(
            {'key': 'tests/test_upload_download_dir.tgz'},
            tmp_dir,
            cache=False
        )
        shutil.rmtree(tmp_dir)
        fb.get_artifact(
            {'key': 'tests/test_upload_download_dir.tgz'},
            tmp_dir
        )

        with open(tmp_filename, 'r') as f:
            line = f.read()

        shutil.rmtree(tmp_dir)
        self.assertTrue(line == random_str)

    def test_get_put_cache(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        strlen = 10000000
        random_str = os.urandom(strlen)

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', 'test_upload_download.txt')

        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb.put_artifact(
            {'key': 'tests/test_upload_download_dir.tgz'},
            tmp_dir,
            cache=False
        )
        shutil.rmtree(tmp_dir)

        tic1 = time.clock()
        fb.get_artifact(
            {'key': 'tests/test_upload_download_dir.tgz'},
            tmp_dir
        )
        tic2 = time.clock()
        fb.get_artifact(
            {'key': 'tests/test_upload_download_dir.tgz'},
            tmp_dir
        )
        tic3 = time.clock()

        with open(tmp_filename, 'r') as f:
            line = f.read()

        shutil.rmtree(tmp_dir)
        self.assertTrue(line == random_str)

        self.assertTrue(tic3 - tic2 < 0.1 * (tic2 - tic1))

    def test_get_artifact_url(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact = {'key': 'tests/test_upload_download.txt'}
        fb.put_artifact(artifact, tmp_filename, cache=False)
        url = fb.get_artifact_url(artifact)
        os.remove(tmp_filename)
        response = requests.get(url)
        self.assertEquals(response.status_code, 200)
        # self.assertEquals(response.content, random_str)
        tar_filename = os.path.join(tempfile.gettempdir(),
                                    'test_upload_download.tgz')
        with open(tar_filename, 'wb') as f:
            f.write(response.content)

        subprocess.call(['tar', '-xzf', tar_filename],
                        cwd=tempfile.gettempdir())

        with open(tmp_filename, 'r') as f:
            self.assertEquals(f.read(), random_str)

        os.remove(tmp_filename)
        os.remove(tar_filename)

    def test_delete_file(self):
        fb = self.get_store()
        tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
        random_str = str(uuid.uuid4())

        os.makedirs(os.path.join(tmp_dir, 'test_dir'))
        tmp_filename = os.path.join(
            tmp_dir, 'test_dir', 'test_upload_download.txt')
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        artifact = {'key': 'tests/test_upload_download_dir.tgz'}
        fb.put_artifact(artifact, tmp_filename, cache=False)
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


class FirebaseArtifactStoreTest(ArtifactStoreTest, unittest.TestCase):
    def get_store(self, config_name='test_config.yaml'):
        config_file = os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)),
            config_name)
        with open(config_file) as f:
            config = yaml.load(f)

        return model.get_db_provider(config).store

    # Tests of private methods

    def test_get_file_url(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('tests/test_upload_download.txt', tmp_filename)

        url = fb._get_file_url('tests/test_upload_download.txt')
        response = requests.get(url)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, random_str)

    def test_get_file_url_auth(self):
        remove_all_keys()
        fb = self.get_store('test_config_auth.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('authtest/test_upload_download.txt', tmp_filename)

        url = fb._get_file_url('authtest/test_upload_download.txt')
        response = requests.get(url)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content, random_str)

    def test_upload_download_file_noauth(self):
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('authtest/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)
        fb._download_file('authtest/test_upload_download.txt', tmp_filename)

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
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('authtest/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)

        # test an authorized attempt to delete file
        remove_all_keys()
        fb = self.get_store('test_config.yaml')
        fb._delete_file('authtest/test_upload_download.txt')
        remove_all_keys()
        fb = self.get_store('test_config_auth.yaml')
        # to make sure file is intact and the same as we uploaded

        fb._download_file('authtest/test_upload_download.txt', tmp_filename)

        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file('authtest/test_upload_download.txt')
        fb._download_file('authtest/test_upload_download.txt', tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))

    def test_upload_download_file(self):
        fb = self.get_store()
        tmp_filename = os.path.join(
            tempfile.gettempdir(),
            'test_upload_download.txt')
        random_str = str(uuid.uuid4())
        with open(tmp_filename, 'w') as f:
            f.write(random_str)

        fb._upload_file('tests/test_upload_download.txt', tmp_filename)
        os.remove(tmp_filename)
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        with open(tmp_filename, 'r') as f:
            line = f.read()
        os.remove(tmp_filename)
        self.assertTrue(line == random_str)

        fb._delete_file('tests/test_upload_download.txt')
        fb._download_file('tests/test_upload_download.txt', tmp_filename)
        self.assertTrue(not os.path.exists(tmp_filename))


if __name__ == "__main__":
    unittest.main()
