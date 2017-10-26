import importlib
import shutil
import pickle
import os
import logging
import sys
import six

from studio import fs_tracker, model

logging.basicConfig()
logger = logging.getLogger('completion_service_client')
try:
    logger.setLevel(model.parse_verbosity(sys.argv[1]))
except BaseException:
    logger.setLevel(10)


def main():
    logger.setLevel(logging.DEBUG)
    logger.debug('copying and importing client module')

    script_path = fs_tracker.get_artifact('clientscript')
    # script_name = os.path.basename(script_path)
    new_script_path = os.path.join(os.getcwd(), '_clientscript.py')
    if os.path.isdir(script_path):
        logger.debug("Script path {} is a directory".format(script_path))
        script_path = os.path.join(script_path,
                                   os.listdir(script_path)[0])
        logger.debug("New script path is " + script_path)

    shutil.copy(script_path, new_script_path)

    script_path = new_script_path
    logger.debug("script path: " + script_path)

    mypath = os.path.dirname(script_path)
    sys.path.append(mypath)
    # os.path.splitext(os.path.basename(script_path))[0]
    module_name = '_clientscript'

    client_module = importlib.import_module(module_name)
    logger.debug('loading args')

    args_path = fs_tracker.get_artifact('args')
    if os.path.isdir(args_path):
        logger.debug("Args path {} is a directory".format(args_path))
        args_path = os.path.join(args_path, os.listdir(args_path)[0])
        logger.debug("New args path is {}".format(args_path))

    with open(args_path, 'rb') as f:
        args = pickle.loads(f.read())

    logger.debug('getting file mappings')
    artifacts = fs_tracker.get_artifacts()
    files = {}
    for tag, path in six.iteritems(artifacts):
        if tag not in {'workspace', 'modeldir', 'tb'}:
            if os.path.isfile(path):
                files[tag] = path
            elif os.path.isdir(path):
                files[tag] = os.path.join(path, os.listdir(path)[0])

    logger.debug('calling client funciton')
    retval = client_module.clientFunction(args, files)

    logger.debug('saving the return value')
    retval_path = fs_tracker.get_artifact('retval')
    if os.path.isdir(fs_tracker.get_artifact('clientscript')):
        # on go runner:
        logger.debug("Running in a go runner, creating {} for retval"
                     .format(retval_path))
        try:
            os.mkdir(retval_path)
        except OSError:
            logger.debug('retval dir present')

        retval_path = os.path.join(retval_path, 'retval')
        logger.debug("New retval_path is {}".format(retval_path))

    logger.debug('Saving retval')
    with open(retval_path, 'wb') as f:
        f.write(pickle.dumps(retval))
    logger.debug('Done')


if __name__ == "__main__":
    main()
