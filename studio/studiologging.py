import os

def get_model_directory():
    return os.environ['TFSTUDIO_MODEL_PATH']

def setup_model_directory(env, experimentName):
    path = os.path.join(os.path.expanduser('~'), '/.tfstudio/models/', experimentName)
    if not os.path.exists(path):
            os.makedirs(path)
    env['TFSTUDIO_MODEL_PATH'] = path


