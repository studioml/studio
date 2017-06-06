import os
import keras
import types

import fs_tracker


class KerasModelWrapper:
    def __init__(self, checkpoint_name, model_dir, json_name='model.json'):
        json_file = os.path.join(model_dir, json_name)
        with open(json_file, 'r') as f:
            self.model = keras.models.model_from_json(f.read())

        self.model.load_weights(checkpoint_name, by_name=True)

    def __call__(self, data):
        if isinstance(data, types.GeneratorType):
            return self.model.predict_generator(data)
        else:
            return self.model.predict(data)


class TensorFlowModelWrapper:
    def __init__(self):
        raise NotImplementedError

    def __call__(self, data):
        raise NotImplementedError
