import importlib
import shutil
import pickle
import os
import sys
import six
import signal
import pdb

from studio import fs_tracker, model, logs, util

logger = logs.getLogger('completion_service_client')
try:
    logger.setLevel(model.parse_verbosity(sys.argv[1]))
except BaseException:
    logger.setLevel(10)


def main():
    logger.debug('copying and importing client module')
    logger.debug('getting file mappings')

    # Register signal handler for signal.SIGUSR1
    # which will invoke built-in Python debugger:
    signal.signal(signal.SIGUSR1, lambda sig, stack: pdb.set_trace())

    artifacts = fs_tracker.get_artifacts()
    files = {}
    logger.debug("Artifacts = {}".format(artifacts))

    for tag, path in six.iteritems(artifacts):
        if tag not in {'workspace', 'modeldir', 'tb', '_runner'}:
            if os.path.isfile(path):
                files[tag] = path
            elif os.path.isdir(path):
                dirlist = os.listdir(path)
                if any(dirlist):
                    files[tag] = os.path.join(
                        path,
                        dirlist[0]
                    )

    logger.debug("Files = {}".format(files))
    script_path = files['clientscript']
    retval_path = fs_tracker.get_artifact('retval')
    util.rm_rf(retval_path)

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

    args_path = files['args']

    with open(args_path, 'rb') as f:
        args = pickle.loads(f.read())

    logger.debug('calling client function')
    retval = client_module.clientFunction(args, files)

    logger.debug('saving the return value')
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
        f.write(pickle.dumps(retval, protocol=2))
    logger.debug('Done')


if __name__ == "__main__":
    main()
