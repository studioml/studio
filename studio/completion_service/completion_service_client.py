import importlib
import shutil
import pickle
import os
import logging
import sys

from studio import fs_tracker, model

logging.basicConfig()
logger = logging.getLogger('completion_service_client')
try:
    logger.setLevel(model.parse_verbosity(sys.argv[1]))
except BaseException:
    logger.setLevel(10)


def main():
    logger.debug('copying and importing client module')

    script_path = fs_tracker.get_artifact('clientscript')
    # script_name = os.path.basename(script_path)
    new_script_path = os.path.join(os.getcwd(), '_clientscript.py')
    shutil.copy(script_path, new_script_path)
    script_path = new_script_path
    logger.debug("script path: " + script_path)

    mypath = os.path.dirname(script_path)
    sys.path.append(mypath)
    # os.path.splitext(os.path.basename(script_path))[0]
    module_name = '_clientscript'

    client_module = importlib.import_module(module_name)
    logger.debug('loading args')
    with open(fs_tracker.get_artifact('args'), 'rb') as f:
        args = pickle.loads(f.read())

    logger.debug('getting file mappings')
    artifacts = fs_tracker.get_artifacts()

    logger.debug('calling client funciton')
    retval = client_module.clientFunction(args, artifacts)

    logger.debug('saving the return value')
    with open(fs_tracker.get_artifact('retval'), 'wb') as f:
        f.write(pickle.dumps(retval))


if __name__ == "__main__":
    main()
