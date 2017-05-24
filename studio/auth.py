import pyrebase
import hashlib
import os
import getpass
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler

token_dir = os.path.join(os.path.expanduser('~'),'.tfstudio/keys')
hour = 3600

class FirebaseAuth(object):
    def __init__(self, firebase):
        if not os.path.exists(token_dir):
            os.makedirs(token_dir)

        self.firebase = firebase
        self._update_user()
        self.sched = BackgroundScheduler()
        self.sched.start()
        self.sched.add_job(self._update_user,  'interval', minutes = 15)
        
        
    def _update_user(self):
        api_key = os.path.join(token_dir, self.firebase.api_key)
        if not os.path.exists(api_key) or (time.time() - os.path.getmtime(api_key)) > hour:
            email = raw_input('Firebase token is not found or expired! You need to re-login. \nemail:')
            password = getpass.getpass('password:')
            self.user = self.firebase.auth().sign_in_with_email_and_password(email, password)
            self.user['email'] = email
        else:
            with open(api_key, 'r') as f:
                olduser = json.load(f)
            self.user = self.firebase.auth().refresh(olduser['refreshToken'])
            self.user['email'] = olduser['email']

        with open(api_key, 'w') as f:
            json.dump(self.user, f)
    
    def get_token(self):
        return self.user['idToken']

    def get_user_id(self):
        return self.user['localId'] if 'localId' in self.user.keys() else self.user['userId']

    def get_user_email(self):
        # we could also use the get_account_info 
        # print self.firebase.auth().get_account_info(self.get_token())
        return self.user['email']

    def __del__(self):
        self.sched.shutdown()

 
