# Setting up a database 
For the moment, tfstudio only supports FireBase (https://firebase.google.com/) as a database/storage backend. 
To configure tfstudio to work with firebase, do the following:

## Creating firebase project and configuring TensorFlow Studio
1. Create a copy of studio/default_config.yaml file. Let's call it new_config.yaml
2. Create a new firebase project: go to https://firebase.google.com, sign in, click add project, specify project name
3. Go to project settings (little cogwheel next to "Overview" on a left-hand pane), tab "General"
4. Copy Web API key and paste it in apiKey of database section of new_config.yaml
5. Copy project ID and paste it in projectId of database section of new_config.yaml 
6. Go to "Cloud messaging tab", copy Sender ID and paste it in messagingSenderId of database sectio of new_config.yaml 

## Configuring users for email / password authentication
Add users. By default, firebase (both database and storage) give read and write access to all authenticated users. 
Go to Authentication in Firebase console (on left-hand pane), tab sign-in methods, and enable email/password method. Then go to users tab, and add users. 
Further, you can customize the database / storage access rules (good read for that is https://firebase.google.com/docs/database/security/ and https://firebase.google.com/docs/storage/security/start)

## Setting up an authentication app for google account authentication
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


## Test run
Go to studio/helloworld/ folder, and try running 

        studio-runner --config /path/to/new_config.yaml train_mnist_keras.py 10
(10 stands for number of training epochs). It should ask for user email and password (if you have uncommented use_email_auth in new_config.yaml), or block to wait for studio to authenticate. Then (or in another terminal) run 

        studio --config /path/to/new_config.yaml
and go to http://localhost:5000 in the browser to see the results of the experiment
    

