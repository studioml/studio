import yaml
from studio import model

with open('/Users/peter.zhokhov/dev/ds-tf-embedding/config.yaml') as f:
    config = yaml.load(f.read())

fb = model.get_db_provider(config)
fb.storage.child('bucket0/test.py').put('download_auth_test.py', fb.auth.get_token())

fb.storage.child('bucket0/test.py').download('aaa.py')

