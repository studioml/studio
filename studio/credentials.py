from . import logs, util
from .model_setup import get_model_verbose_level

AWS_KEY = 'aws_access_key'
AWS_SECRET_KEY = 'aws_secret_key'
ACCESS_USER = 'access_user'
ACCESS_PASSWORD = 'access_password'
KEY_CREDENTIALS = 'credentials'
KEY_AUTHENTICATION = 'authentication'

# Credentials encapsulates the logic
# of basic access credentials handling
# for different kinds of studioml storage providers (S3, http, local etc.)
class Credentials(object):
    def __init__(self, cred_dict):
        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())

        if cred_dict is not None and isinstance(cred_dict, str):
            if cred_dict == 'none':
                cred_dict = None
            else:
                msg: str =\
                    "NOT SUPPORTED credentials format {0}".format(cred_dict)
                util.report_fatal(msg, self.logger)

        self.key = None
        self.secret_key = None

        if cred_dict is not None:
            if ACCESS_USER in cred_dict.keys():
                self.key = cred_dict.get(ACCESS_USER)
            elif AWS_KEY in cred_dict.keys():
                self.key = cred_dict.get(AWS_KEY)

            if ACCESS_PASSWORD in cred_dict.keys():
                self.secret_key = cred_dict.get(ACCESS_PASSWORD)
            elif AWS_SECRET_KEY in cred_dict.keys():
                self.secret_key = cred_dict.get(AWS_SECRET_KEY)

    def get_key(self):
        return self.key

    def get_secret_key(self):
        return self.secret_key

    def to_dict(self):
        result = dict()
        if self.key is not None:
            result[ACCESS_USER] = self.key
        if self.secret_key is not None:
            result[ACCESS_PASSWORD] = self.secret_key
        return result

    @classmethod
    def getCredentials(cls, config):
        if config is None:
            return None
        cred_dict = config.get(KEY_CREDENTIALS, None)
        if cred_dict is None:
            cred_dict = config.get(KEY_AUTHENTICATION, None)

        return Credentials(cred_dict) if cred_dict else None

