import argparse
import sys
import os
import time
import json
import glob
import traceback
import logging
import importlib

from flask import Flask, request
from studio import fs_tracker

logging.basicConfig()

# `studio serve <key> --preprocessing blabla.py ` under the hood will run something like
# studio run --reuse <key>/modeldir:modeldata _serve.py  --preprocessing blabla.py

app = Flask(__name__)
model = None
logger = None

def get_logger():
    global logger
    if not logger:
        logger = logging.getLogger('studio-serve')
        logger.setLevel(logging.DEBUG)  
    return logger

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
              
        
def main():
    argparser = argparse.ArgumentParser(
        description='Serve studio model'
    )

    argparser.add_argument(
        '--preprocessing', '-p',
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

    options = argparser.parse_args(sys.argv[1:])

    global model

    if options.preprocessing:
        prep_module_name = importlib.import_module(options.preprocessing)
        model = prep_module_name.create_model(fs_tracker.get_artifact('modeldata'))
    else:
        model = auto_generate_model()

    app.run()
    


def auto_generate_model():
    modeldir = fs_tracker.get_artifact('modeldata')
    
    hdf5_files = [
            (p, os.path.getmtime(p))
            for p in
            glob.glob(modeldir + '/*.hdf*') +
            glob.glob(modeldir + '/*.h5')]
    if any(hdf5_files):
        # experiment type - keras
        get_logger().info("Loading keras model (using b64 encoding and pickle)")
        import keras
        last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
        keras_model = keras.models.load_model(last_checkpoint)
        return wrap_keras_model(keras_model)

    return lambda x: x

def wrap_keras_model(keras_model):
    import base64

    pipe = ModelPipe()
    pipe.add(lambda d: pickle.loads(base64.b64decode(d)))
    pipe.add(model)
    pipe.add(lambda d: pickle.dumps(base64.b64encode(d)))

    return pipe

               

if __name__ == '__main__':
    main()
 
 


