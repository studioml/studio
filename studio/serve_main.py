import argparse
import sys
import os
import time
import json
import glob
import traceback
import importlib
import pickle
import re
import threading

from flask import Flask, request
from . import fs_tracker, logs
from .model_util import ModelPipe

app = Flask(__name__)
model = None
logger = None

killtimer = None
killtimer_duration = None


def get_logger():
    global logger
    if not logger:
        logger = logs.getLogger('studio-serve')
        logger.setLevel(logs.DEBUG)
    return logger


def restart_killtimer(duration=None):
    global killtimer
    global killtimer_duration

    def killtriger():
        get_logger().info('Shutting down due to inactivity')
        os._exit(0)

    if killtimer:
        killtimer.cancel()

    if duration:
        killtimer_duration = duration
    else:
        duration = killtimer_duration

    get_logger().info('Initializing kill timer for {} s'
                      .format(duration))
    killtimer = threading.Timer(duration, killtriger)
    killtimer.start()


@app.route('/', methods=['POST'])
def inference():
    try:
        tic = time.time()
        input_dict = request.json
        output_dict = model(input_dict)
        return json.dumps(output_dict)
    except BaseException as e:
        return json.dumps({
            'error': traceback.format_exc(e)
        })
    finally:
        get_logger().info('inference completed in {} s'
                          .format(time.time() - tic))

        restart_killtimer()


def main():
    argparser = argparse.ArgumentParser(
        description='Serve studio model'
    )

    argparser.add_argument(
        '--wrapper', '-w',
        help='python script with function create_model ' +
             'that takes modeldir '
        '(that is, directory where experiment saves ' +
        'the checkpoints etc)' +
        'and returns dict -> dict function (model).' +
        'By default, studio-serve will try to determine ' +
        'this function automatically.',
        default=None
    )

    argparser.add_argument('--port',
                           help='port to run Flask server on',
                           type=int,
                           default=5000)

    argparser.add_argument('--host',
                           help='host name.',
                           default='0.0.0.0')

    argparser.add_argument(
        '--killafter',
        help='Shut down after this many seconds of inactivity',
        default=3600)

    options = argparser.parse_args(sys.argv[1:])

    global model

    modeldir = fs_tracker.get_artifact('modeldata')
    if options.wrapper:
        module_name = re.sub('.py\Z', '', options.wrapper)
        wrapper_module = importlib.import_module(module_name)
        model = wrapper_module.create_model(modeldir)
    else:
        model = auto_generate_model(modeldir)

    restart_killtimer(int(options.killafter))
    app.run(host=options.host, port=options.port)


def auto_generate_model(modeldir):
    if modeldir is not None:
        hdf5_files = [
            (p, os.path.getmtime(p))
            for p in
            glob.glob(modeldir + '/*.hdf*') +
            glob.glob(modeldir + '/*.h5')]
        if any(hdf5_files):
            # experiment type - keras
            get_logger().info("Loading keras model " +
                              "(using pickle serialization)")
            import keras
            last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
            keras_model = keras.models.load_model(last_checkpoint)
            print(keras_model)
            keras_model.summary()
            return wrap_keras_model(keras_model)

    return lambda x: x


def wrap_keras_model(keras_model):
    pipe = ModelPipe()
    pipe.add(lambda d: pickle.loads(d))
    pipe.add(keras_model)
    pipe.add(lambda d: pickle.dumps(d))

    return pipe


if __name__ == '__main__':
    main()
