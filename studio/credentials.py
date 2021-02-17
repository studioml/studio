from . import logs, util
from .model_setup import get_model_verbose_level

AWS_KEY = 'access_key'
AWS_SECRET_KEY = 'secret_access_key'
KEY_CREDENTIALS = 'credentials'
AWS_TYPE = 'aws'

# Credentials encapsulates the logic
# of basic access credentials handling
# for different kinds of studioml storage providers (S3, http, local etc.)
class Credentials(object):
    def __init__(self, cred_dict):
        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(get_model_verbose_level())

        self.type = None
        self.key = None
        self.secret_key = None
        if cred_dict is None:
            return

        if isinstance(cred_dict, str) and cred_dict == 'none':
            return

        if not isinstance(cred_dict, dict):
            msg: str =\
                "NOT SUPPORTED credentials format {0}".format(repr(cred_dict))
            util.report_fatal(msg, self.logger)

        if len(cred_dict) == 1 and AWS_TYPE in cred_dict.keys():
            aws_creds = cred_dict[AWS_TYPE]
            self.type = AWS_TYPE
            self.key = aws_creds.get(AWS_KEY, None)
            self.secret_key = aws_creds.get(AWS_SECRET_KEY, None)
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

    def to_dict(self):
        return {
            self.type: {
                AWS_KEY: self.key,
                AWS_SECRET_KEY: self.secret_key
            }
        }

    @classmethod
    def getCredentials(cls, config):
        if config is None:
            return None
        cred_dict = config.get(KEY_CREDENTIALS, None)
        return Credentials(cred_dict) if cred_dict else None

