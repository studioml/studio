import requests
import json

import logging
logging.basicConfig()

import model

class HTTPProvider(object):
    """Data provider for Postgres."""

    def __init__(self, config):
        # TODO: implement connection
        self.url = config.get('serverUrl')
        self.auth = None
        self.logger = logging.getLogger('HTTPProvider')
        self.logger.setLevel(10)

    def add_experiment(self, experiment):
        headers = self._get_headers()
        request = requests.post(self.url + '/api/add_experiment', 
            headers=headers,
            data=json.dumps({"experiment":experiment.__dict__})
        )

        self._raise_detailed_error(request)       
        import pdb
        pdb.set_trace()
        print request

            

    def delete_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment 
        else:
            key = experiment.key

        headers = self._get_headers()
        requests.post(self.url + '/api/delete_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )

    def get_experiment(self, experiment):
        if isinstance(experiment, str):
            key = experiment 
        else:
            key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/get_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )
    
        self._raise_detailed_error(request)
        return model.experiment_from_dict(request.json()['experiment'])
    
    def _raise_detailed_error(self, request):
        if request.status_code != 200:
            raise ValueError(request.message)

        data = request.json()
        if data['status'] == 'ok':
            return

        raise ValueError(data['status'])

    def _get_headers(self):
        return {"content-type":"application/json"}
 
    def start_experiment(self, experiment):
        raise NotImplementedError()

    def stop_experiment(self, experiment):
        raise NotImplementedError()

    def finish_experiment(self, experiment):
        raise NotImplementedError()

    def get_user_experiments(self, user):
        raise NotImplementedError()

    def get_projects(self):
        raise NotImplementedError()

    def get_project_experiments(self):
        raise NotImplementedError()

    def get_artifacts(self):
        raise NotImplementedError()

    def get_users(self):
        raise NotImplementedError()

    def checkpoint_experiment(self, experiment):
        raise NotImplementedError()

    def refresh_auth_token(self, email, refresh_token):
        raise NotImplementedError()

    def get_auth_domain(self):
        raise NotImplementedError()

