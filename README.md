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

## Authentication 
Both studio and studio-runner use same authentication tokens for database backend. The tokens are valid for 1 hour, 
but if studio / studio-runner is running, it renews tokens automatically. 
Note that expiration tokens don't expire; this also means that you can use tokens on multiple machines (i.e. when you want to use google account authentication on a remote server and don't want to open extra ports) - simply copy contents of ~/.tfstudio/keys folder to another machine. 
For now TensorFlow studio supports 2 methods of authentication: email/password and using google account.
If you don't have a user account set up, and don't have a google account, you can uncomment "guest: true" line
 in the database section of studio/default_config.yaml file to use studio-runner and studio in the guest mode. 

Alternatively, you can set up your own database (with blackjack and hook... let's not get distracted here) and configure 
tfstudio to use it. See the "Setting up a database" paragraph below. This is also a preferred option if you don't want to
share the models / artifacts with everyone. 


### Email / password authentication
If you have an email/password account set up, you can use this method. In default_config.yaml file uncomment "use_email_auth: true" 
line in database section. If the token is not found or expired when you run studio / studio-runner, either of the commands will ask
for email and password and use that to authenticate. Note that the password is NOT stored on your computer (but tokens are), 
that's why it keeps asking for password if inactive for more than an hour. 

### Google account authentication
If you don't have an email/password account set up, don't despair! Any user with a google account can use TensorFlow studio as a 
first-class citizen. If token not found when you run studio, Web UI will redirect you to the authentication app which will
ask to sign in with your google account, and issues an authentication token. Then studio / studio-runner can use that token. 

## Setting up a database 
For the moment, tfstudio only supports FireBase (https://firebase.google.com/) as a database/storage backend. 
To configure tfstudio to work with firebase, do the following:

### Creating firebase project and configuring TensorFlow Studio
1. Create a copy of studio/default_config.yaml file. Let's call it new_config.yaml
2. Create a new firebase project: go to https://firebase.google.com, sign in, click add project, specify project name
3. Go to project settings (little cogwheel next to "Overview" on a left-hand pane), tab "General"
4. Copy Web API key and paste it in apiKey of database section of new_config.yaml
5. Copy project ID and paste it in projectId of database section of new_config.yaml 
6. Go to "Cloud messaging tab", copy Sender ID and paste it in messagingSenderId of database sectio of new_config.yaml 

### Configuring users for email / password authentication
Add users. By default, firebase (both database and storage) give read and write access to all authenticated users. 
Go to Authentication in Firebase console (on left-hand pane), tab sign-in methods, and enable email/password method. Then go to users tab, and add users. 
Further, you can customize the database / storage access rules (good read for that is https://firebase.google.com/docs/database/security/ and https://firebase.google.com/docs/storage/security/start)

### Setting up an authentication app for google account authentication
1. Install Firebase CLI (https://firebase.google.com/docs/cli/)
2. We will be deploying a firebase app, so the following is the summary of (https://firebase.google.com/docs/hosting/deploying). The app iteslf is a modified authentication code example from here: https://firebase.google.com/docs/samples/
3. Go to studio/auth folder and run 

        firebase init
4. Select Hosting, press Enter
5. Select the right firebase project (if you have more than one)
6. Answer 'N' to the remaining questions
7. Run 
    
        firebase deploy
8. To test successful deployment, go the <hosting_url>/index.html url (where hosting_url was output by firebase deploy). You should see page titled "Firebase Authentication" that either has a button "SIGN IN" or "SIGN OUT" and your authentication details below. 


### Test run
Go to studio/helloworld/ folder, and try running 

        studio-runner --config /path/to/new_config.yaml train_mnist_keras.py 10
(10 stands for number of training epochs). It should ask for user email and password (if you have uncommented use_email_auth in new_config.yaml), or block to wait for studio to authenticate. Then (or in another terminal) run 

        studio --config /path/to/new_config.yaml
and go to http://localhost:5000 in the browser to see the results of the experiment
    
## Setting up a remote worker
### Getting credentials 
1. Remote workers work by listening to distributed queue. Right now the distributed queue is backed by Google PubSub; so to access it, you'll need application credentials from Google. (in the future, it may be implemented via firebase itself, in which case this step should become obsolete). If you made it this far, you are likely to have a google cloud compute account set up; but even if not, go to http://cloud.google.com and either set up an account or sign in. 
2. Next, create a project if you don't have a project corresponding to studio just yet. 
3. Then go to API Manager -> Credentials, and click "Create credentials" -> "Service account key"
4. Choose "New service account" from the "Select accout" dropdown,  and keep key type as JSON
5. Enter a name of your liking for account (google will convert it to a uniqie name), and choose "PubSub Editor" for a role (technically, you can create 2 keys, and keep publisher on a machine that submits work, and subscriber key on a machine that implements the work)
6. Save a json credentials file
7. Add GOOGLE_APPLICATION_CREDENTIALS variable to the environment that points to the saved json credentials file both on work submitter and work implementer. 

### Setting up remote worker
1. Install docker, and nvidia-docker to use gpus
2. Clone the repo

    git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e .

3. Generate the docker image:

    cd docker && docker build -t tfstudio/base:0.0 . 

4. Start worker (queue name is a name of the queue that will definte where submit work to)
    
    studio-start-rworker <queue-name>

### Submitting work
On a submitting machine (usually local):

    studio-runner --queue <queue-name> script.py <script_args>

This script should quit promptly, but you'll be able to see experiment progress in studio web ui 
