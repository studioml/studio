import os
import getpass
import time
import json
import shutil
import atexit
import tempfile
import requests
import re
import uuid

from builtins import input

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except BaseException:
    BackgroundScheduler = None

import google.auth.transport.requests
import google.oauth2.id_token

from studio.util.util import rand_string, check_for_kb_interrupt
from studio import pyrebase
from studio.util import logs


TOKEN_DIR = os.path.expanduser('~/.studioml/keys')

HOUR = 3600
HALF_HOUR = 1800
API_KEY_COOLDOWN = 900
SLEEP_TIME = 0.5
MAX_NUM_RETRIES = 100


_auth_singleton = None

_grequest = google.auth.transport.requests.Request()


def get_auth_class(authtype):
    if authtype is None:
        return None
    elif authtype.lower() == 'none':
        return None
    elif authtype.lower() == 'firebase':
        return FirebaseAuth
    elif authtype.lower() == 'github':
        return GithubAuth
    else:
        raise ValueError(
            'Unknown authentication type {}, valid values are none, ' +
            'firebase, github'
            .format(authtype))


def get_auth(
        config,
        blocking=True,
        verbose=logs.DEBUG):

    global _auth_singleton
    if _auth_singleton is None:
        if isinstance(config, dict):
            auth_class = get_auth_class(config['type'])
        else:
            auth_class = get_auth_class(config)

        if auth_class:
            _auth_singleton = auth_class(
                config,
                blocking=blocking,
                verbose=verbose
            )
        else:
            return None
    return _auth_singleton


def get_and_verify_user(request, authtype):
    if not request.headers or 'Authorization' not in request.headers.keys():
        return None

    token = request.headers['Authorization'].split(' ')[-1]
    if not token or token == 'null':
        return None

    authclass = get_auth_class(authtype)
    if not authclass:
        return None

    if request.json:
        refresh_token = request.json.get('refreshToken')
    else:
        refresh_token = None

    return authclass.verify_token(token, refresh_token)


class GithubAuth(object):

    def __init__(
        self,
        config,
        blocking=True,
        verbose=logs.DEBUG
    ):
        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        if isinstance(config, dict):
            self.config = config
        else:
            self.config = {'type': config}

        self.tokendir = os.path.abspath(os.path.expanduser(
            self.config.get('token_directory', TOKEN_DIR))
        )

        if not os.path.exists(self.tokendir):
            os.makedirs(self.tokendir)

        self.token = self._load_token()[0]
        if self.token is None and blocking:
            self._sign_in()

    def get_user_id(self):
        return self.userid

    def get_token(self):
        if self.token is None:
            self.token = self._load_token()[0]

        return self.token

    def get_user_email(self):
        return self.userid

    def refresh_token(self, userid, refreshtoken):
        pass

    def is_expired(self):
        return False

    def _load_token(self):
        tokendir_contents = os.listdir(self.tokendir)
        tokens = [
            f for f in tokendir_contents
            if os.path.isfile(os.path.join(self.tokendir, f)) and
            f.endswith('.githubtoken')
        ]

        # TODO selection out of multiple token files
        if not any(tokens):
            return None, None

        token_file = os.path.join(self.tokendir, tokens[0])
        with open(token_file) as f:
            token = f.read().strip()

        self.userid = self.verify_token(token)
        if self.userid != re.sub(r'.githubtoken\Z', '', tokens[0]):
            self.logger.error(
                'Token filename does not match github login'
            )
            return None, None

        return token, token_file

    def get_token_file(self):
        return self._load_token()[1]

    def _save_token(self):
        if self.token is None:
            return

        token_file = os.path.join(self.tokendir, self.userid + '.githubtoken')
        with open(token_file, 'w') as f:
            f.write(self.token)

    def _sign_in(self):
        print(
            '*** \n' +
            'Sign in with your GitHub username and password \n' +
            'NOTE: studio.ml does NOT store GitHub passwords ' +
            ' or any other passwords for that matter. \n ' +
            'Your ' +
            'password will be used a single time to generate ' +
            'an authorization token that allows studio to '
            'verify your identity in the future.'
        )

        while True:
            self.userid = input('user id:')
            password = getpass.getpass('password:')

            response = requests.post(
                'https://api.github.com/authorizations',
                json={
                    'scopes': ['read:user'],
                    'note': 'studioml authorization, ' +
                            'random = ' + str(uuid.uuid4())
                },
                auth=(self.userid, password),
            )

            password = None

            if response.status_code == 201:
                self.token = response.json()['token']
                self._save_token()
                print('Successfully created token with name: ' +
                      response.json()['app']['name'])
                return

            else:
                print("GitHub login failure")
                print(response.json())

    @staticmethod
    def verify_token(token, refresh_token=None):
        response = requests.get(
            'https://api.github.com/user',
            headers={"Authorization": "Bearer " + token}
        )

        if response.status_code != 200:
            return None
        else:
            return response.json()['login']


class FirebaseAuth(object):
    def __init__(
            self,
            config,
            blocking=True,
            verbose=logs.DEBUG):
        if not os.path.exists(TOKEN_DIR):
            try:
                os.makedirs(TOKEN_DIR)
            except OSError:
                pass

        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(logs.DEBUG)

        self.firebase = pyrebase.initialize_app(config)
        self.user = {}
        self.use_email_auth = config.get('use_email_auth', False)
        if self.use_email_auth:
            self.email = config.get('email', None)
            self.password = config.get('password', None)
            if not self.password or not self.email:
                self.email = input(
                    'Firebase token is not found or expired! ' +
                    'You need to re-login. (Or re-run with ' +
                    'studio/studio-runner ' +
                    'with --guest option ) '
                    '\nemail:')
                self.password = getpass.getpass('password:')

        self.expired = True
        self.token_file = os.path.join(TOKEN_DIR, self.firebase.api_key)
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
        self.sched.add_job(self._update_user, 'interval', minutes=31)
        atexit.register(self.sched.shutdown)

    def _update_user(self):
        if not os.path.exists(self.token_file):
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
                    with open(self.token_file) as f:
                        user = json.loads(f.read())
                except BaseException as e:
                    check_for_kb_interrupt()
                    self.logger.info(e)
                    time.sleep(SLEEP_TIME)
                    counter += 1
            if user is None:
                return

            self.user = user
            if time.time() > self.user.get('expiration', 0):
                counter = 0
                while counter < MAX_NUM_RETRIES:
                    try:
                        self.refresh_token(user['email'], user['refreshToken'])
                        break
                    except BaseException as e:
                        check_for_kb_interrupt()
                        self.logger.info(e)
                        time.sleep(SLEEP_TIME)
                        counter += 1
            else:
                self.expired = False

    def sign_in_with_email(self):
        self.user = \
            self.firebase.auth().sign_in_with_email_and_password(
                self.email,
                self.password)

        # TODO check if credentials worked

        self.user['email'] = self.email

    def refresh_token(self, email, refresh_token):
        self.user = self.firebase.auth().refresh(refresh_token)
        self.user['email'] = email
        self.user['expiration'] = time.time() + API_KEY_COOLDOWN
        self.expired = False

        # if not os.path.exists(api_key) or \
        #   time.time() - os.path.getmtime(api_key) > HALF_HOUR:
        # Rename to ensure atomic writes to json file
        # (technically more safe, but slower)

        tmp_api_key = os.path.join(tempfile.gettempdir(),
                                   "api_key_%s" % rand_string(32))
        with open(tmp_api_key, 'w') as f:
            f.write(json.dumps(self.user))
            f.flush()
            os.fsync(f.fileno())
            f.close()
        os.rename(tmp_api_key, self.token_file)

    def get_token(self):
        if self.expired:
            return None
        return self.user['idToken']

    def get_token_file(self):
        return self.token_file

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

    def is_expired(self):
        return self.expired

    @staticmethod
    def verify_token(token, refresh_token=None):
        claims = google.oauth2.id_token.verify_firebase_token(
            token, _grequest)

        if not claims:
            return None
        else:
            if refresh_token:
                refresh_token(claims['email'], refresh_token)

            # get_db().register_user(claims['user_id'], claims['email'])

            return claims['user_id']


def remove_all_keys():
    keypath = os.path.join(os.path.expanduser('~'), '.studioml', 'keys')
    if os.path.exists(keypath):
        try:
            shutil.rmtree(keypath)
        except OSError:
            pass
