Setting up a database
=====================

This page describes the process of setting up your own database /
storage for the models. This puts you in full control of who has access
to the experiment data. For the moment, Studio only supports Firebase
(https://firebase.google.com/) as a database/storage backend. To
configure Studio to work with Firebase, do the following:

Creating a Firebase project and configuring Studio
--------------------------------------------------

1. Create a copy of studio/default\_config.yaml file. Let's call it
   new\_config.yaml
2. Create a new Firebase project: go to https://firebase.google.com,
   sign in, click add project, specify project name
3. Go to project settings (little cogwheel next to "Overview" on the
   left-hand pane), tab "General"
4. Copy the Web API key and paste it in apiKey of the database section of
   new\_config.yaml
5. Copy the project ID and paste it in projectId of the database section of
   new\_config.yaml
6. Go to "Cloud messaging tab", copy the Sender ID and paste it in
   messagingSenderId of the database section of new\_config.yaml

Configuring users
-----------------

To enable email/password authentication within the Firebase client
uncomment the use\_email\_auth tag in your new\_config.yaml. Add
users. By default, Firebase (both database and storage) grants read and
write access to all authenticated users. Go to Authentication in the Firebase
console (on left-hand pane), tab sign-in methods, and enable methods
that you would like to use. 

For now, Studio supports Google account
authentication and email/password authentication. If you have choosen
to use the email/password method for authentication, use the Users tab
of the Authentication panel to manually add yourself with a password.
This password is not shared by other Google services. If this is what
you want then Google account based authentication is needed, therefore
you should always use a unique password. Further, you can customize the
database / storage access rules (good resources are
https://firebase.google.com/docs/database/security/ and
https://firebase.google.com/docs/storage/security/start). The default
rules allow read and write access to all authenticated users, to both
storage and database. This might not be the behaviour you 
want because then users can freely delete / modify each other's experiments. 

To make experiments readable by everyone, but writeable only
by the creator, slightly more sophisticated rules are needed. Examples of such
rules (that are used at the default Studio Firebase app) are given in
``auth/firebase_db.rules`` and ``auth/firebase_storage.rules`` for
database and storage.

Setting up an authentication app for Google account authentication
------------------------------------------------------------------

1.  Create a new Firebase project from the [console]
    (https://console.firebase.google.com)
2.  Under the authentication tab in the console, turn on the Google
    authentication provider
3.  Install the Firebase CLI (https://firebase.google.com/docs/cli/)
4.  We will be deploying a Firebase app, so the following is the summary
    of (https://firebase.google.com/docs/hosting/deploying). The app
    iteslf is a modified authentication code example from here:
    https://firebase.google.com/docs/samples/
5.  Go to the studio/auth folder and run

    ::

        firebase init

6.  Select Hosting by pressing space, press Enter to continue
7.  Select the right Firebase project (if you have more than one)
8.  Answer 'N' to the remaining questions
9.  Run

    ::

        firebase deploy

10. To test successful deployment, go the /index.html url (where
    hosting\_url was output by Firebase deploy). You should see a page
    titled "Firebase Authentication" that either has a button "SIGN IN"
    or "SIGN OUT" and your authentication details below.

Test run
--------

Go to the studio/helloworld/ folder, and run

::

        studio run --config /path/to/new_config.yaml train_mnist_keras.py 10
        

where 10 is the number of training epochs. You should be prompted
for your user email and password (if you have uncommented
use\_email\_auth in new\_config.yaml), or block to wait for Studio to
authenticate. When entering email/password combinations you may be
prompted several times to enter your details. Then (or in another
terminal) run

::

        studio ui --config /path/to/new_config.yaml
        

and go to http://localhost:5000 in the browser to see the results of the
experiment.
