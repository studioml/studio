Setting up a database
=====================

This page describes the process of setting up your own database /
storage for the models. This puts you in full control of who has access
to the experiment data. For the moment, tfstudio only supports FireBase
(https://firebase.google.com/) as a database/storage backend. To
configure tfstudio to work with firebase, do the following:

Creating firebase project and configuring TensorFlow Studio
-----------------------------------------------------------

1. Create a copy of studio/default\_config.yaml file. Let's call it
   new\_config.yaml
2. Create a new firebase project: go to https://firebase.google.com,
   sign in, click add project, specify project name
3. Go to project settings (little cogwheel next to "Overview" on a
   left-hand pane), tab "General"
4. Copy Web API key and paste it in apiKey of database section of
   new\_config.yaml
5. Copy project ID and paste it in projectId of database section of
   new\_config.yaml
6. Go to "Cloud messaging tab", copy Sender ID and paste it in
   messagingSenderId of database section of new\_config.yaml

Configuring users
-----------------

To enable email/password authentication within the Firebase client
uncommented the use\_email\_auth tag in your new\_config.yaml. Add
users. By default, firebase (both database and storage) grants read and
write access to all authenticated users Go to Authentication in Firebase
console (on left-hand pane), tab sign-in methods, and enable methods
that you would like to use. For now, studio supports google account
authentication, and email/password authentication. If you have choosen
to use the email/password method for authentication, use the Users tab
of the Authentication panel to manually add yourself with a password.
This password is not shared by other google services, if this is what
you want then google account based authentication is needed, therefore
you should always use a unique password. Further, you can customize the
database / storage access rules (good read for that is
https://firebase.google.com/docs/database/security/ and
https://firebase.google.com/docs/storage/security/start) The default
rules allow read and write access to all authenticated users, to both
storage and database. This might not be quite the behaviour that you
would want, because then users can freely delete / modify experiments of
each other. To make experiments readable by everyone, but writeable only
by creator, a bit more involved rules are needed. The examples of such
rules (that are used at the default studio firebase app) are given in
``auth/firebase_db.rules`` and ``auth/firebase_storage.rules`` for
database and storage.

Setting up an authentication app for google account authentication
------------------------------------------------------------------

1.  Create a new Firebase project from the [console]
    (https://console.firebase.google.com)
2.  Under the authentication tab in the console, turn on the Google
    authentication provider
3.  Install Firebase CLI (https://firebase.google.com/docs/cli/)
4.  We will be deploying a firebase app, so the following is the summary
    of (https://firebase.google.com/docs/hosting/deploying). The app
    iteslf is a modified authentication code example from here:
    https://firebase.google.com/docs/samples/
5.  Go to studio/auth folder and run

    ::

        firebase init

6.  Select Hosting by pressing space, press Enter to continue
7.  Select the right firebase project (if you have more than one)
8.  Answer 'N' to the remaining questions
9.  Run

    ::

        firebase deploy

10. To test successful deployment, go the /index.html url (where
    hosting\_url was output by firebase deploy). You should see page
    titled "Firebase Authentication" that either has a button "SIGN IN"
    or "SIGN OUT" and your authentication details below.

Test run
--------

Go to the studio/helloworld/ folder, and run

::

        studio run --config /path/to/new_config.yaml train_mnist_keras.py 10
        

(10 stands for the number of training epochs). You should be prompted
for your user email and password (if you have uncommented
use\_email\_auth in new\_config.yaml), or block to wait for studio to
authenticate. When entering email/password combinations you may be
prompted several times to enter your details. Then (or in another
terminal) run

::

        studio ui --config /path/to/new_config.yaml
        

and go to http://localhost:5000 in the browser to see the results of the
experiment.
