import hashlib
from typing import Dict

from studio.util import logs, util
from studio.storage import storage_setup

AWS_KEY = 'access_key'
AWS_SECRET_KEY = 'secret_access_key'
AWS_SESSION_TOKEN = 'session_token'
AWS_REGION = 'region'
AWS_PROFILE = 'profile'
KEY_CREDENTIALS = 'credentials'
AWS_TYPE = 'aws'

# Credentials encapsulates the logic
# of basic access credentials handling
# for different kinds of studioml storage providers (S3, http, local etc.)
class Credentials:
    def __init__(self, cred_dict):
        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(storage_setup.get_storage_verbose_level())

        self.type = None
        self.key = None
        self.secret_key = None
        self.session_token = None
        self.region = None
        self.profile = None
        if cred_dict is None:
            return

        if isinstance(cred_dict, str) and cred_dict == 'none':
            return

        if not isinstance(cred_dict, dict):
            msg: str =\
                "NOT SUPPORTED credentials format {0}".format(repr(cred_dict))
            util.report_fatal(msg, self.logger)

        if len(cred_dict) == 0:
            # Empty credentials dictionary is like None:
            return

        if len(cred_dict) == 1 and AWS_TYPE in cred_dict.keys():
            aws_creds = cred_dict[AWS_TYPE]
            self.type = AWS_TYPE
            self.key = aws_creds.get(AWS_KEY, None)
            self.secret_key = aws_creds.get(AWS_SECRET_KEY, None)
            self.session_token = aws_creds.get(AWS_SESSION_TOKEN, None)
            self.region = self._get_named(AWS_REGION, aws_creds)
            self.profile = self._get_named(AWS_PROFILE, aws_creds)

            if self.key is None or self.secret_key is None:
                msg: str = \
                    "INVALID aws credentials format {0}".format(repr(cred_dict))
                util.report_fatal(msg, self.logger)
        else:
            msg: str =\
                "NOT SUPPORTED credentials format {0}".format(repr(cred_dict))
            util.report_fatal(msg, self.logger)

    def get_type(self):
        return self.type

    def get_key(self):
        return self.key

    def get_secret_key(self):
        return self.secret_key

    def get_session_token(self):
        return self.session_token

    def get_region(self):
        return self.region

    def get_profile(self):
        return self.profile

    def _get_named(self, key: str, config: Dict):
        value = config.get(key, None)
        if value is None:
            value = config.get(key+'_name', None)
        return value

    def to_dict(self):
        result: Dict = {
            self.type: {
                AWS_KEY: self.key,
                AWS_SECRET_KEY: self.secret_key
            }
        }
        if self.session_token is not None:
            result[self.type][AWS_SESSION_TOKEN] = self.session_token
        if self.region is not None:
            result[self.type][AWS_REGION] = self.region
        if self.profile is not None:
            result[self.type][AWS_PROFILE] = self.profile
        return result

    def get_fingerprint(self) -> str:
        if self.type is None and self.key is None and\
            self.secret_key is None:
            return ''
        id_str: str = "{0}::{1}::{2}::{3}::{4}::{5}"\
            .format(self.type, self.key, self.secret_key,
                    self.session_token,
                    self.profile, self.region)
        return hashlib.sha256(id_str.encode()).hexdigest()

    @classmethod
    def get_credentials(cls, config):
        if config is None:
            return None
        cred_dict = config.get(KEY_CREDENTIALS, None)
        return Credentials(cred_dict) if cred_dict else None

    def to_string(self):
        return "type: {0} key: {1} secret: <reducted> profile: {2} region: {3}"\
            .format(self.type, self.key, self.profile, self.region)
