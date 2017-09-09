import importlib
import shutil
import pickle
from studio import fs_tracker

shutil.copy(fs_tracker.get_artifact('clientscript'), './_clientfile.py')
client_module = importlib.import_module('_clientfile')
# os.remove('_clientfile.py')

retval = client_module.clientFunction()

with open(fs_tracker.get_artifact('retval'), 'w') as f:
    f.write(pickle.dumps(retval))




