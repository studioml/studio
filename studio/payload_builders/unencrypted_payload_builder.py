from studio.payload_builders.payload_builder import PayloadBuilder
from studio.experiments.experiment import Experiment

class UnencryptedPayloadBuilder(PayloadBuilder):
    """
    Simple payload builder constructing
    unencrypted experiment payloads.
    """
    def construct(self, experiment: Experiment, config, packages):
        return { 'experiment': experiment.to_dict(),
                 'config': config}
