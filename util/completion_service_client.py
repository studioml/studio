import importlib
import shutil
import pickle
import os
import logging
from studio import fs_tracker

logging.basicConfig()

logger = logging.getLogger('completion_service_client')
logger.setLevel(10)

logger.debug('copying and importing client module')
shutil.copy(fs_tracker.get_artifact('clientscript'), './_clientfile.py')
client_module = importlib.import_module('_clientfile')
os.remove('_clientfile.py')

logger.debug('loading args')
with open(fs_tracker.get_artifact('args')) as f:
    args = pickle.loads(f.read())

logger.debug('getting file mappings')
artifacts = fs_tracker.get_artifacts()

logger.debug('calling client funciton')
retval = client_module.clientFunction(args, artifacts)

logger.debug('saving the return value')
with open(fs_tracker.get_artifact('retval'), 'w') as f:
    f.write(pickle.dumps(retval))
