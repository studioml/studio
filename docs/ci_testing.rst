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

    docker image build --tag [dockerhubUsername]/standalone_testing:latest . -f Dockerfile_standalone_testing

This creates a docker image on your local docker, for docker commands you may need to use sudo before the command.

Then create a Dockerhub repository with the name standalone_testing. Push the image to your Dockerhub repository with 

::

    docker push [dockerhubUsername]/standalone_testing


To run the tests edit ``test-runner.yaml:56`` to 

::

    - image: [dockerhubUsername]/standalone_testing

Additionally you may have to edit the names in the yaml file as they may conflict with existing namespaces and resources that might already be running on your kubernetes cluster

Finally use

::

    kubectl apply -f test-runner.yaml
    
while in the root studio directory to automatically run tests,

results can be seen using 

::

    kubectl logs test-runner-xxxxxxx-xxxxx

where the last values are the id of your image

To stop deployment use 

::

    kubectl delete deployment test-runner
