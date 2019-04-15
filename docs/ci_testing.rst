Requirements: Docker, Dockerhub Account, Kubernetes, Keel

https://docs.docker.com/install/

https://keel.sh/v1/guide/installation.html

https://kubernetes.io/docs/tasks/tools/install-kubectl/

https://keel.sh/v1/guide/installation.html

To run individual tests, edit the Dockerfile_standalone_testing.

After editing build the image using
"docker image build --tag [dockerhubUsername]/standalone_testing:latest . -f Dockerfile_standalone_testing"

May have to use sudo

Push the image to your docker account with 

"docker push [dockerhubUsername]/standalone_testing"

Then to run the tests edit the test-runner.yaml:56 to 

"- image: [dockerhubUsername]/standalone_testing"

Finally use "kubectl apply -f test-runner.yaml" to automatically run tests,

results can be seen using "kubectl log test-runner-xxxxxxx-xxxxx"
