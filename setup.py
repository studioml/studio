from setuptools import setup
from pip.req import parse_requirements

install_reqs = parse_requirements('requirements.txt', session='hack')

# reqs is a list of requirement
# e.g. ['django==1.5.1', 'mezzanine==1.4.6']
reqs = [str(ir.req) for ir in install_reqs]


setup(name='tfstudio',
      version='0.0',
      description='TensorFlow Studio',
      long_description='TensorFlow model and data management tool',
      url='https://github.com/ilblackdragon/studio',
      packages=['studio'],
      install_requires=reqs,
      scripts=['studio/scripts/studio',
               'studio/scripts/studio-run',
               'studio/scripts/studio-ui',
               'studio/scripts/studio-local-worker',
               'studio/scripts/studio-remote-worker',
               'studio/scripts/studio-start-remote-worker',
               'studio/scripts/studio-add-credentials'],
      tests_suite='nose.collector',
      tests_require=['nose'],
      include_package_data=True,
      zip_safe=False)
