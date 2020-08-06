Tests only be run from the in the main studio directory
use "python -m pytest tests/{testname}" to run individual tests
use "python -m pytest tests" to run all tests

Be sure to install additional Python dependencies for running tests
by:

pip install -r test_requirements.txt

Also you would have to set cloud environment and credentials in test_config.yaml
prior to running tests.
Verify also that "studio" executable is in your PATH
to be able to run local_worker test.


