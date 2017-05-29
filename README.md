# TensorFlow Studio

Model management tools.

## Installation:
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


