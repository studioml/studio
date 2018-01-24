import unittest
import subprocess
import time
from random import randint
import os
import uuid
import requests

from studio import model


@unittest.skipIf('GOOGLE_APPLICATION_CREDENTIALS' not in os.environ.keys(),
                 "GOOGLE_APPLICATION_CREDENTIALS is missing, needed for " +
                 "server to communicate with storage")
class ServingTest(unittest.TestCase):

    _mutliprocess_shared_ = True

    def _test_serving(self, data_in, expected_data_out, wrapper=None):

        self.port = randint(5000, 9000)
        server_experimentid = 'test_serving_' + str(uuid.uuid4())

        args = [
            'studio', 'run',
            '--force-git',
            '--verbose=debug',
            '--experiment=' + server_experimentid,
            '--config=' + self.get_config_path(),
            'studio::serve_main',
            '--port=' + str(self.port),
            '--host=localhost'
        ]

        if wrapper:
            args.append('--wrapper=' + wrapper)

        subprocess.Popen(args, cwd=os.path.dirname(__file__))
        time.sleep(60)

        try:
            retval = requests.post(
                url='http://localhost:' + str(self.port), json=data_in)
            data_out = retval.json()
            assert data_out == expected_data_out

        finally:
            with model.get_db_provider(model.get_config(
                    self.get_config_path())) as db:

                db.stop_experiment(server_experimentid)
                time.sleep(20)
                db.delete_experiment(server_experimentid)

    def test_serving_identity(self):
        data = {"a": "b"}
        self._test_serving(
            data_in=data,
            expected_data_out=data
        )

    def test_serving_increment(self):
        data_in = {"a": 1}
        data_out = {"a": 2}

        self._test_serving(
            data_in=data_in,
            expected_data_out=data_out,
            wrapper='model_increment.py'
        )

    def get_config_path(self):
        return os.path.join(
            os.path.dirname(__file__),
            'test_config_http_client.yaml'
        )


if __name__ == '__main__':
    unittest.main()
