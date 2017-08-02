# TensorFlow Studio
Model management tools.

<p align="center">
  <img src="logo.png" width="250"/>
</p>

## Main features
* Capturing experiment information (python environment, files, dependencies, logs) with no invasion in the experiment code
* Web dashboard to monitor and organize experiments that integrates with TensorBoard
* Running experiments locally, remotely or in the cloud (google cloud or Amazon EC2) (more details [here](docs/cloud.md) and [here](docs/remote_worker.md))
* Artifact management and persistence (more details [here](docs/artifacts.md))
* Hyperparameter search (more details [here](docs/hyperparams.md))
* Customizable python environment for remote workers (more details [here](docs/customenv.md))

## Example usage

Start visualizer:

    studio ui

Run your jobs:

    studio run myfile.py

You can see results of your job at http://127.0.0.1:5000. 
Run `studio {ui|run} --help` for a full list of ui / runner options

## Installation
### Setting up virtualenv (recommended)
If you don't want to set up a new virtual environment, feel free to skip this step 
and go to the next section. 

Create new virtual environment:
    
    virtualenv --python=python2.7 tfstudio

Activate it. If you are using plain python:
    
    . tfstudio/bin/activate    

Or, if you are using anaconda:

    . ./tfstudio/bin/activate

Upgrade pip:

    pip install --upgrade pip

### Installation
Once open, we'll publish package to PyPI. For now, pip install it from the git project directory:

    git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e . 

### Running tests
To run the unit and regression tests (for now, we have little difference - some tests take longer than others, but that's about it), run 

    python $(which nosetests) --processes=8 --process-timeout=600

Note that simply `nosetests` tends not to use virtualenv correctly (hence a more extended version of the call). If you have application credentials configured 
to work with distributed queues and cloud workers, those will be tested as well, otherwise, respective tests will be skipped. Total test runtime (when run in parallel 
as in command line above) should be no more than 10 minutes. Most of the tests are I/O limited, so parallel execution speeds up things quite a bit. The longest test is
gpu cloud worker test in EC2 cloud (takes about 500 seconds due to installation of the drivers / CUDA on the EC2 instance).

## Authentication 
Both studio ui and studio runner use same authentication tokens for database backend. The tokens are valid for 1 hour, 
but if studio ui / studio runner is running, it renews tokens automatically. 
Note that refresh tokens don't expire; this also means that you can use tokens on multiple machines (i.e. when you want to use google account authentication on a remote server and don't want to open extra ports) - simply copy contents of ~/.tfstudio/keys folder to another machine. 
For now TensorFlow studio supports 2 methods of authentication: email/password and using google account.
If you don't have a user account set up, and don't have a google account, you can uncomment "guest: true" line
 in the database section of studio/default_config.yaml file to use studio runner and studio ui in the guest mode. 

Alternatively, you can set up your own database (with blackjack and hook... let's not get distracted here) and configure 
tfstudio to use it. See [setting up database](docs/setup_database.md). This is also a preferred option if you don't want to
share the models / artifacts with everyone. 


### Email / password authentication
If you have an email/password account set up, you can use this method. In default_config.yaml file uncomment "use_email_auth: true" 
line in database section. If the token is not found or expired when you run studio ui / studio runner, either of the commands will ask
for email and password and use that to authenticate. Note that the password is NOT stored on your computer (but tokens are), 
that's why it keeps asking for password if inactive for more than an hour. 

### Google account authentication
If you don't have an email/password account set up, don't despair! Any user with a google account can use TensorFlow studio as a 
first-class citizen. If token not found when you run studio, Web UI will redirect you to the authentication app which will
ask to sign in with your google account, and issues an authentication token. Then studio ui / studio runner can use that token. 

## Further reading and cool features
TensorFlow studio allows one to run experiments remotely. The process of setting up a server is described [here](docs/remote_worker.md). 

The experiments can also be run using google cloud compute with configurable instances. The user manual is [here](docs/cloud.md), and 
the setup instructions are here [for Google Cloud](docs/gcloud_setup.md) and [for Amazon EC2](docs/ec2_setup.md)

Another very important aspect of model management is management of artifacts (data, resulting weights etc). The facilities that tfstudio
provides in that regard are described [here](docs/artifacts.md)

Hyperparameter search features are described [here](docs/hyperparams.md)



