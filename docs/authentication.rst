Authentication
==============

Currently, Studio uses GitHub auth for authentication. For command-line tools
(studio ui, studio run etc) the authentication is done via personal 
access tokens. When no token is present (e.g. when you run studio for
the first time), you will be asked to input your github username and 
password. Studio DOES NOT store your username or password, instead, 
those are being sent to GitHub API server in exchange to an access token. 
The access token is being saved and used from that point on.
The personal access tokens do not expire, can be transferred from one 
machine to another, and, if necessary, can be revoked by going to 
GitHub -> Settings -> Developer Settings -> Personal Access Tokens

Authentication for the hosted UI server (https://zoo.studio.ml) follows
the standard GitHub Auth flow for web apps. 
