from .payload_builder import PayloadBuilder

class UnencryptedPayloadBuilder(PayloadBuilder):
    """
    Simple payload builder constructing
    unencrypted experiment payloads.
    """
    def __init__(self, name: str):
        super(UnencryptedPayloadBuilder, self).__init__(name)

    def construct(self, experiment, config, packages):
        return { 'experiment': experiment.__dict__,
                 'config': config}






