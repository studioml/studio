# TensorFlow Studio

Model management tools.

## Setting up virtualenv (recommended)
If you don't want to set up a new virtual environment, feel free to skip this step 
and go to the next section. 

Create new virtual environment:
    
    virtualenv tfstudio

Activate it. On Mac OS X:
    
    source activate tfstudio

On Linux:

    . ./tfstuio/bin/activate

Upgrade pip:

    pip install --upgrade pip

## Installation
Once open, we'll publish package to PyPI. For now, pip install it from the git project directory:

    git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e . 


## Example usage

Start visualizer:

    studio 

Run your jobs:

    stuido-runner myfile.py --some-arg=value --learning_rate=0.3

You can see results of your job at http://127.0.0.1:5000

Both studio and studio-runner use same authentication tokens for database backend. First time you run either of the commands,
you will be asked for an email and a password corresponding to a database user. The resulting token is valid for 1 hour, 
but if studio keeps running, it renews tokens automatically. 
If you don't have a user account set up, you can uncomment guest=true line in the database section of studio/default_config.yaml file
to use studio-runner and studio in the guest mode. 

Alternatively, you can set up your own database (with blackjack and hook... let's not get distracted here) and configure 
tfstudio to use it. See the paragraph below. 

## Setting up a database 
For the moment, tfstudio only supports FireBase (https://firebase.google.com/) as a database/storage backend. 
To configure tfstudio to work with firebase, do the following:

1. Create a copy of studio/default_config.yaml file. Let's call it new_config.yaml
2. Create a new firebase project: go to https://firebase.google.com, sign in, click add project, specify project name
3. Go to project settings (little cogwheel next to "Overview" on a left-hand pane), tab "General"
4. Copy Web API key and paste it in apiKey of database section of new_config.yaml
5. Copy project ID and paste it in projectId of database section of new_config.yaml 
6. Go to "Cloud messaging tab", copy Sender ID and paste it in messagingSenderId of database sectio of new_config.yaml 
7. Add users. By default, firebase (both database and storage) give read and write access to all authenticated users. Go to Authentication in Firebase console (on left-hand pane), tab sign-in methods, and enable email/password method. Then go to users tab, and add users. 
8. Test run. If you have not modified access rights of the database, a few unit tests won't work (unit tests assume guest access to the database, which is blocked by default). Instead, go to studio/helloworld/ folder, and try running 
        studio-runner --config /path/to/new_config.yaml train_mnist_keras.py 10
(10 stands for number of training epochs). It should ask for user email and password. Then (or in another terminal) run 

        studio --config /path/to/new_config.yaml
and go to localhost:5000 in the browser to see the results of the experiment
    



