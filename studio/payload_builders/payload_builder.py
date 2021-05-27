class PayloadBuilder:
    """
    Abstract class representing
    payload object construction from experiment components.
    Result is payload ready to be submitted for execution.
    """
    def __init__(self, name: str):
        self.name = name if name else 'NO NAME'

    def construct(self, experiment, config, packages):
        raise NotImplementedError(
            'Not implemented for payload builder {0}'.format(self.name))
