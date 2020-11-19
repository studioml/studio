from .payload_builder import PayloadBuilder
from .experiment import Experiment

class UnencryptedPayloadBuilder(PayloadBuilder):
    """
    Simple payload builder constructing
    unencrypted experiment payloads.
    """
    def __init__(self, name: str):
        super().__init__(name)

    def construct(self, experiment: Experiment, config, packages):
        return { 'experiment': experiment.to_dict(),
                 'config': config}






