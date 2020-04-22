class WorkloadModifier:
    """
    Abstract class representing
    a potential modification to workload request
    before it is submitted for execution.
    """
    def __init__(self, name: str):
        self.name = name if name else 'NO NAME'

    def modify(self, workload):
        raise NotImplementedError(
            'Not implemented for workload modifier {0}'.format(self.name))








