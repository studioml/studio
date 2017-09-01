======================
Command-line interface
======================

In some cases, a (semi-)programmatic way of keeping track of experiments may be preferred. On top of the Python and HTTP API, we provide
a command-line tool to get a quick overview of exising experiments and take actions on them. Commands available 
at the moment are:

- ``studio runs list users`` - lists all users 
- ``studio runs list projects`` - lists all projects
- ``studio runs list [user]`` - lists your (default) or someone else's experiments
- ``studio runs list project <project>`` - lists all experiments in a project
- ``studio runs list all`` - lists all experiments

- ``studio runs kill <experiment>`` - deletes experiment
- ``studio runs stop <experiment>`` - stops experiment

Note that for now if the experiment is running, killing it will NOT automatically stop the runner. You should stop the experiment first, ensure its status has been changed to stopped, and then kill it. This is a known issue, and we are working on a solution. 




