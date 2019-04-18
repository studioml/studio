CI Testing
==============

Requirements: Docker, Dockerhub Account, Kubernetes, Keel

https://docs.docker.com/install/

https://hub.docker.com/

https://keel.sh/v1/guide/installation.html

https://kubernetes.io/docs/tasks/tools/install-kubectl/


By default all tests will run, to run individual tests, edit the last line of Dockerfile_standalone_testing to
::

    CMD python -m pytest tests/[testName].py
    
To build the docker image use

::

    docker image build --tag [dockerhubUsername]/standalone_testing:latest . -f Dockerfile_standalone_testing_[dockerhubUsername]

Then create a Dockerhub repository with the name standalone testing. Push the image to your Dockerhub repository with 

::

    docker push [dockerhubUsername]/standalone_testing


Then to run the tests edit the ``test-runner.yaml:56`` to 

::

    - image: [dockerhubUsername]/standalone_testing

Finally use

::

    kubectl apply -f test-runner.yaml
    
while in the root studio directory to automatically run tests,

results can be seen using 

::

    kubectl logs test-runner-xxxxxxx-xxxxx

where the last values are the id of your image
