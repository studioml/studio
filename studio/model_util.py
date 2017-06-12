import types
try:
    import keras
except ImportError:
    keras = None


class KerasModelWrapper:
    def __init__(self, checkpoint_name):
        self.model = keras.models.load_model(checkpoint_name)

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
