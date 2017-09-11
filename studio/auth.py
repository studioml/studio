import os
import getpass
import time
import json
import shutil
import atexit
import tempfile
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except BaseException:
    BackgroundScheduler = None

from util import rand_string

TOKEN_DIR = os.path.expanduser('~/.studioml/keys')
HOUR = 3600
API_KEY_COOLDOWN = 900
SLEEP_TIME = 0.5
MAX_NUM_RETRIES = 100


class FirebaseAuth(object):
    def __init__(
            self,
            firebase,
            use_email_auth=False,
            email=None,
            password=None,
            blocking=True):
        if not os.path.exists(TOKEN_DIR):
            os.makedirs(TOKEN_DIR)

        self.firebase = firebase
        self.user = {}
        self.use_email_auth = use_email_auth
        if use_email_auth:
            if email and password:
                self.email = email
                self.password = password
            else:
                self.email = raw_input(
                    'Firebase token is not found or expired! ' +
                    'You need to re-login. (Or re-run with ' +
                    'studio/studio-runner ' +
                    'with --guest option ) '
                    '\nemail:')
                self.password = getpass.getpass('password:')

        self.expired = True
        self._update_user()

        if self.expired and blocking:
            print('Authentication required! Either specify ' +
                  'use_email_auth in config file, or run '
                  'studio and go to webui ' +
                  '(localhost:5000 by default) '
                  'to authenticate using google credentials')
            while self.expired:
                time.sleep(1)
                self._update_user()

        self.sched = BackgroundScheduler()
        self.sched.start()
        self.sched.add_job(self._update_user, 'interval', minutes=59)
        atexit.register(self.sched.shutdown)

    def _update_user(self):
        api_key = os.path.join(TOKEN_DIR, self.firebase.api_key)
        if not os.path.exists(api_key):
                # refresh tokens don't expire, hence we can
                # use them forever once obtained
                # or (time.time() - os.path.getmtime(api_key)) > HOUR:
            if self.use_email_auth:
                self.sign_in_with_email()
                self.expired = False
            else:
                self.expired = True
        else:
            # If json file fails to load, try again
            counter = 0
            user = None
            while True:
                if user is not None or counter >= MAX_NUM_RETRIES:
                    break
                try:
                    with open(api_key, 'rb') as f:
                        user = json.load(f)
                except BaseException:
                    time.sleep(SLEEP_TIME)
                    counter += 1
            if user is None:
                return

            self.user = user
            self.expired = False
            if time.time() - os.path.getmtime(api_key) > API_KEY_COOLDOWN:
                counter = 0
                while counter < MAX_NUM_RETRIES:
                    try:
                        self.refresh_token(user['email'], user['refreshToken'])
                    except BaseException:
                        time.sleep(SLEEP_TIME)
                        counter += 1
                    else:
                        return

    def sign_in_with_email(self):
        self.user = \
            self.firebase.auth().sign_in_with_email_and_password(
                self.email,
                self.password)

        # TODO check if credentials worked

        self.user['email'] = self.email

    def refresh_token(self, email, refresh_token):
        api_key = os.path.join(TOKEN_DIR, self.firebase.api_key)
        self.user = self.firebase.auth().refresh(refresh_token)
        self.user['email'] = email
        self.expired = False

        if not os.path.exists(api_key) or \
           time.time() - os.path.getmtime(api_key) > HOUR:
            # Rename to ensure atomic writes to json file
            # (technically more safe, but slower)
            tmp_api_key = os.path.join(tempfile.gettempdir(),
                                       "api_key_%s" % rand_string(32))
            with open(tmp_api_key, 'wb') as f:
                json.dump(self.user, f)
                f.flush()
                os.fsync(f.fileno())
                f.close()
            os.rename(tmp_api_key, api_key)

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


def remove_all_keys():
    keypath = os.path.join(os.path.expanduser('~'), '.studioml', 'keys')
    if os.path.exists(keypath):
        shutil.rmtree(keypath)
