Authentication
==============

Both ``studio ui`` and ``studio run`` use the same authentication tokens for
a database backend. The tokens are valid for one hour, but if Studio is
running, it renews the tokens automatically.

Note that refresh tokens do not expire; this means you can use these
tokens on multiple machines, e.g. when you want to use a Google account
authentication on a remote server but don't want to open extra ports.
Simply copy the contents of ~/.studioml/keys folder to the desired
machine.

Currently, Studio supports 2 methods of authentication: email & password
and using a Google account. To use ``studio run`` and ``studio ui`` in guest
mode, in studio/default\_config.yaml, uncomment "guest: true" under the
database section.

Alternatively, you can set up your own database and configure Studio to
use it. See `setting up database <http://docs.studio.ml/en/latest/setup_database.html>`__. This is the
preferred option if you want to keep your models and artifacts private.

Email / password authentication
-------------------------------

If you have an email & password account set up, you can use this method.
In ``default\_config.yaml``, uncomment "use\_email\_auth: true" under the
database section. If the token is not found or expired when you run
``studio ui`` / ``studio run``, you will be asked for your email and password
for authentication. Note that the password is NOT stored on your
computer (but tokens are), so you will be asked for your password after
an hour of inactivity.

Google account authentication
-------------------------------

If you don't have an email & password account set up, don't despair! Any
user with a Google account can use Studio as a first-class citizen. If a
token is not found when you run studio, the Web UI will redirect you to
the Google account authentication app where you will be issued a new
authentication token.

