class DependencyPolicy:
    """
    Abstract class representing some policy
    for generating Python packages dependencies
    to be used for submitted experiment.
    """

    def generate(self, resources_needed):
        raise NotImplementedError('Not implemented DependencyPolicy')
