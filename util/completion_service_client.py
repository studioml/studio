import importlib
from studio import fs_tracker

client_module = importlib.import_module(fs_tracker.get_artifact('clientfile'))
retval = client_module.clientFunction()

with open(fs_tracker.get_artifact('retval'), 'w') as f:
    f.write(pickle.dumps(retval))




