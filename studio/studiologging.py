import os

def get_model_directory(experimentName = None):
    if experimentName:
        return os.path.join(os.path.expanduser('~'), '.tfstudio/models/', experimentName)
    else:
        return os.environ['TFSTUDIO_MODEL_PATH']

def setup_model_directory(env, experimentName):
    path = get_model_directory(experimentName)
    if not os.path.exists(path):
            os.makedirs(path)
    env['TFSTUDIO_MODEL_PATH'] = path


