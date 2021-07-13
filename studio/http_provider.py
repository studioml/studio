import requests
import json
import time
import re

from studio.util import logs
from studio.auth import get_auth
from studio.credentials.credentials import Credentials
from studio.storage.storage_setup import get_storage_verbose_level
from studio.storage.http_storage_handler import HTTPStorageHandler
from studio.experiments.experiment import experiment_from_dict
from studio.util.util import retry, check_for_kb_interrupt


class HTTPProvider(object):
    """Data provider communicating with API server."""

    def __init__(
            self,
            config,
            verbose=10,
            blocking_auth=True,
            compression=None):
        # TODO: implement connection
        self.url = config.get('serverUrl', None)
        self.verbose = get_storage_verbose_level()
        self.logger = logs.get_logger('HTTPProvider')
        self.logger.setLevel(self.verbose)

        self.credentials: Credentials = \
            Credentials.get_credentials(config)

        self.storage_handler = HTTPStorageHandler(
            self.url,
            self.credentials.to_dict() if self.credentials else None,
            compression=compression)

        self.auth = None
        guest = config.get('guest', None)
        if not guest and 'serviceAccount' not in config.keys():
            self.auth = get_auth(
                config.get('authentication', None),
                blocking_auth
            )

        self.compression = compression
        if self.compression is None:
            self.compression = config.get('compression', None)

    def add_experiment(self, experiment, userid=None,
                       compression=None):

        headers = self._get_headers()
        compression = compression if compression else self.compression

        for tag, art in experiment.artifacts.items():
            if not art.is_mutable and art.local_path is not None:
                art.hash = art.get_hash(art.local_path)

        data = {}
        data['experiment'] = experiment.__dict__
        data['compression'] = compression

        def post_request():
            request = requests.post(
                self.url + '/api/add_experiment',
                headers=headers,
                data=json.dumps(data))

            self._raise_detailed_error(request)
            return request

        request = retry(
            post_request,
            no_retries=10,
            sleep_time=10,
            logger=self.logger)

        artifacts = request.json()['artifacts']

        self._update_artifacts(experiment, artifacts)

    def _update_artifacts(self, experiment, artifacts):
        self.logger.debug(str(experiment.artifacts.keys()))
        self.logger.debug(str(artifacts.keys()))

        for tag, art in experiment.artifacts.items():
            target_art = artifacts.get(tag)
            if target_art is not None:
                art.key = target_art.key
                art.remote_path = target_art.remote_path

                if art.local_path is not None:
                    art.upload(art.local_path)

    def delete_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment
        else:
            key = experiment.key

        headers = self._get_headers()

        def post_request():
            request = requests.post(self.url + '/api/delete_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key})
                                    )
            self._raise_detailed_error(request)

        post_request()
        # retry(post_request, sleep_time=10, logger=self.logger)

    def get_experiment(self, experiment, getinfo='True'):
        if isinstance(experiment, str):
            key = experiment
        else:
            key = experiment.key

        headers = self._get_headers()
        try:
            request = requests.post(self.url + '/api/get_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key})
                                    )

            self._raise_detailed_error(request)
            data = request.json()['experiment']
            return experiment_from_dict(data)
        except BaseException as e:
            check_for_kb_interrupt()
            self.logger.info('error getting experiment {}'.format(key))
            self.logger.info(e)
            return None

    def start_experiment(self, experiment):
        self.checkpoint_experiment(experiment)
        if isinstance(experiment, str):
            key = experiment
        else:
            key = experiment.key

        headers = self._get_headers()

        def post_request():
            request = requests.post(self.url + '/api/start_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key})
                                    )
            self._raise_detailed_error(request)
        retry(post_request, sleep_time=10, logger=self.logger)

        if not isinstance(experiment, str):
            experiment.time_started = time.time()

    def stop_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment
        else:
            key = experiment.key

        headers = self._get_headers()

        def post_request():
            request = requests.post(self.url + '/api/stop_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key})
                                    )
            self._raise_detailed_error(request)

        retry(post_request, sleep_time=10, logger=self.logger)

    def finish_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment
        else:
            key = experiment.key

        headers = self._get_headers()

        def post_request():
            request = requests.post(self.url + '/api/finish_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key})
                                    )
            self._raise_detailed_error(request)

        retry(post_request, sleep_time=10, logger=self.logger)
        if not isinstance(experiment, str):
            experiment.time_finished = time.time()

    def get_user_experiments(self, user=None, blocking=True):
        headers = self._get_headers()
        user = user if user else self._get_userid()

        response = requests.post(
            self.url + '/api/get_user_experiments',
            headers=headers,
            data=json.dumps({"user": user}))

        self._raise_detailed_error(response)
        data = response.json()['experiments']

        experiments = data

        return experiments

    def get_projects(self):
        headers = self._get_headers()
        response = requests.post(
            self.url + '/api/get_projects',
            headers=headers)

        self._raise_detailed_error(response)
        projects = response.json()['projects']

        return projects

    def get_project_experiments(self, project):
        headers = self._get_headers()
        response = requests.post(
            self.url + '/api/get_project_experiments',
            headers=headers,
            data=json.dumps({"project": project}))

        self._raise_detailed_error(response)
        data = response.json()['experiments']

        experiments = data
        return experiments

    def get_artifacts(self, key):
        return {t: a['url'] for t, a in
                self.get_experiment(key).artifacts.items()}

    def get_artifact(self, artifact,
                     local_path=None, only_newer='True'):

        if isinstance(artifact, str):
            experiment_key = re.match(r'.*(?=/)', artifact).group(0)
            artifact_tag = re.search(r'(?<=/)[^/]*\Z', artifact).group(0)
            experiment = self.get_experiment(experiment_key)
            artifact = experiment.artifacts[artifact_tag]

        return artifact.download(local_path=local_path, only_newer=only_newer)

    def get_users(self):
        headers = self._get_headers()
        response = requests.post(
            self.url + '/api/get_users',
            headers=headers)

        self._raise_detailed_error(response)
        users = response.json()['users']

        return users

    def checkpoint_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment
            experiment = self.get_experiment(key)
        else:
            key = experiment.key

        headers = self._get_headers()

        def post_request():
            request = requests.post(self.url + '/api/checkpoint_experiment',
                                    headers=headers,
                                    data=json.dumps({"key": key}))

            self._raise_detailed_error(request)
            artifacts = request.json()['artifacts']
            return artifacts

        artifacts = retry(post_request, sleep_time=10, logger=self.logger)

        self._update_artifacts(experiment, artifacts)
        experiment.time_last_checkpoint = time.time()

    def refresh_auth_token(self, email, refresh_token):
        if self.auth:
            self.auth.refresh_token(email, refresh_token)

    def register_user(self, userid, email):
        pass

    def _get_headers(self):
        headers = {"content-type": "application/json"}
        if self.auth:
            token = self.auth.get_token()
            if token:
                headers["Authorization"] = "Firebase " + token
        return headers

    def _get_userid(self):
        userid = None
        if self.auth:
            userid = self.auth.get_user_id()
        userid = userid if userid else 'guest'
        return userid

    def _raise_detailed_error(self, request):
        if request.status_code != 200:
            raise ValueError(str(request.__dict__))

        data = request.json()
        if 'status' in data.keys():
            if data['status'] == 'ok':
                return

            raise ValueError(data['status'])
        else:
            raise ValueError(json.dumps(data))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
