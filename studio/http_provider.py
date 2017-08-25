import requests
import json

import logging
logging.basicConfig()

import model
import pyrebase

from auth import FirebaseAuth

class HTTPProvider(object):
    """Data provider for Postgres."""

    def __init__(self, config, store, blocking_auth=True):
        # TODO: implement connection
        self.url = config.get('serverUrl')
        self.auth = None
        self.logger = logging.getLogger('HTTPProvider')
        self.logger.setLevel(10)
    
        self.auth = None
        self.app = pyrebase.initialize_app(config)
        guest = config.get('guest')
        if not guest and 'serviceAccount' not in config.keys():
            self.auth = FirebaseAuth(self.app,
                                     config.get("use_email_auth"),
                                     config.get("email"),
                                     config.get("password"),
                                     blocking_auth)


        self.store = store

    def add_experiment(self, experiment):
        headers = self._get_headers()
        request = requests.post(self.url + '/api/add_experiment', 
            headers=headers,
            data=json.dumps({"experiment":experiment.__dict__})
        )

        self._raise_detailed_error(request)       
        artifacts = request.json()['artifacts']
 
        for tag,art in experiment.artifacts.iteritems():
            art['key'] = artifacts[tag]['key']
            art['qualified'] = artifacts[tag]['qualified']
            art['bucket'] = artifacts[tag]['bucket']
            
            self.store.put_artifact(art)
        
            
    def delete_experiment(self, experiment):
        if isinstance(experiment, basestring):
            key = experiment 
        else:
            key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/delete_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )
        self._raise_detailed_error(request)

    def get_experiment(self, experiment):
        if isinstance(experiment, basestring):
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
    
 
    def start_experiment(self, experiment):
        self.checkpoint_experiment(experiment)
        if isinstance(experiment, basestring):
            key = experiment 
        else:
            key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/start_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )
        self._raise_detailed_error(request)

    def stop_experiment(self, experiment):
        key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/stop_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )
        self._raise_detailed_error(request)

    def finish_experiment(self, experiment):
        self.checkpoint_experiment(experiment)
        if isinstance(experiment, basestring):
            key = experiment 
        else:
            key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/finish_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )
        self._raise_detailed_error(request)


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
        if isinstance(experiment, basestring):
            key = experiment
            experiment = self.get_experiment(key)
        else:
            key = experiment.key

        headers = self._get_headers()
        request = requests.post(self.url + '/api/checkpoint_experiment', 
            headers=headers,
            data=json.dumps({"key":key})
        )

        self._raise_detailed_error(request)       
        artifacts = request.json()['artifacts']
 
        for tag,art in experiment.artifacts.iteritems():
            if 'local' in art.keys():
                art['key'] = artifacts[tag]['key']
                art['qualified'] = artifacts[tag]['qualified']
                art['bucket'] = artifacts[tag]['bucket']
            
                self.store.put_artifact(art)


    def refresh_auth_token(self, email, refresh_token):
        raise NotImplementedError()

    def get_auth_domain(self):
        raise NotImplementedError()

    def _get_headers(self):
        return {"content-type":"application/json"}

    def _raise_detailed_error(self, request):
        if request.status_code != 200:
            raise ValueError(request.message)

        data = request.json()
        if data['status'] == 'ok':
            return

        raise ValueError(data['status'])


