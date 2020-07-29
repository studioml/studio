import re

class DependencyPolicy(object):
    """
    Policy for adjusting experiment dependencies
    to specific execution environment and required resources.
    """

    def __init__(self, resources_needed):
        self.resources_needed = resources_needed

    def process(self, packages):
        result = []
        for pkg in packages:
            if pkg.startswith('-e git+'):
                # git package
                result.append(pkg)
            elif '==' in pkg:
                # pypi package
                pkey = re.search(r'^.*?(?=\=\=)', pkg).group(0)
                pversion = re.search(r'(?<=\=\=).*\Z', pkg).group(0)

                if self.resources_needed is not None and \
                        int(self.resources_needed.get('gpus')) > 0:
                    if (pkey == 'tensorflow' or pkey == 'tf-nightly'):
                        pkey = pkey + '-gpu'

                # TODO add installation logic for torch
                result.append(pkey + '==' + pversion)
        return result
