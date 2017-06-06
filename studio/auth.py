import os
import getpass
import time
import json
from apscheduler.schedulers.background import BackgroundScheduler

token_dir = os.path.join(os.path.expanduser('~'), '.tfstudio/keys')
hour = 3600


class FirebaseAuth(object):
    def __init__(self, firebase, email=None, password=None):
        if not os.path.exists(token_dir):
            os.makedirs(token_dir)

        self.firebase = firebase
        self.user = {}
        self.email = email
        self.password = password
        self.expired = True
        self._update_user()
        self.sched = BackgroundScheduler()
        self.sched.start()
        self.sched.add_job(self._update_user, 'interval', minutes=5)

    def _update_user(self):
        api_key = os.path.join(token_dir, self.firebase.api_key)
        if not os.path.exists(api_key) or \
               (time.time() - os.path.getmtime(api_key)) > 900:
            self.sign_in_with_email()
            self.expired = False
            #self.expired = True
        else:
            with open(api_key, 'r') as f:
                user = json.load(f)
            print(api_key)
            print(user)
            refresh_token(user['email'], user['refreshToken'])


    def sign_in_with_email(self):
        email = raw_input(
            'Firebase token is not found or expired! ' +
            'You need to re-login. (Or re-run with studio/studio-runner ' +
            'with --guest option ) '
            '\nemail:') if not self.email else self.email

        password = getpass.getpass('password:') \
            if not self.password else self.password
        self.user = \
            self.firebase.auth().sign_in_with_email_and_password(
                email,
                password)
           
            # TODO check if credentials worked

        self.user['email'] = email

    def refresh_token(self, email, refresh_token):
        api_key = os.path.join(token_dir, self.firebase.api_key)
        self.user = self.firebase.auth().refresh(refresh_token)
        self.user['email'] = email
        self.expired = False
        with open(api_key, 'w') as f:
                json.dump(self.user, f)

    def get_token(self):
        if self.expired:
            return None
        return self.user['idToken']

    def get_user_id(self):
        if self.expired:
            return None

        if 'localId' in self.user.keys():
            return self.user['localId']

        return self.user['userId']

    def get_user_email(self):
        if self.expired:
            return None
        # we could also use the get_account_info
        # print self.firebase.auth().get_account_info(self.get_token())
        return self.user['email']

    def __del__(self):
        self.sched.shutdown()
