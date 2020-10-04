import re

try:
    try:
        from pip._internal.operations import freeze
    except Exception:
        from pip.operations import freeze
except ImportError:
    freeze = None

from .dependencies_policy import DependencyPolicy

class StudioDependencyPolicy(DependencyPolicy):
    """
    StudioML policy for adjusting experiment dependencies
    to specific execution environment and required resources.
    """

    def __init__(self):
        super(DependencyPolicy, self).__init__()

    def generate(self, resources_needed):
        if freeze is None:
            raise ValueError(
                "freeze operation is not available for StudioDependencyPolicy")

        needs_gpu = self._needs_gpu(resources_needed)
        packages = freeze.freeze()
        result = []
        for pkg in packages:
            if self._is_special_reference(pkg):
                # git repo or directly installed package
                result.append(pkg)
            elif '==' in pkg:
                # pypi package
                pkey = re.search(r'^.*?(?=\=\=)', pkg).group(0)
                pversion = re.search(r'(?<=\=\=).*\Z', pkg).group(0)

                if needs_gpu and \
                        (pkey == 'tensorflow' or pkey == 'tf-nightly'):
                    pkey = pkey + '-gpu'

                # TODO add installation logic for torch
                result.append(pkey + '==' + pversion)
        return result

    def _is_special_reference(self, pkg: str):
        if pkg.startswith('-e git+'):
            return True
        if 'git+https://' in pkg or 'file://' in pkg:
            return True
        return False

    def _needs_gpu(self, resources_needed):
        return resources_needed is not None and \
            int(resources_needed.get('gpus')) > 0

