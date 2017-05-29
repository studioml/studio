# TensorFlow Studio

Model management tools.

## Installation:
Once open, we'll publish package to PyPI. For now, pip install it from the git project directory:

    git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e . 

## Example usage

Start visualizer:

    studio --port=8888

Run your jobs:

    stuido-runner myfile.py --some-arg=value --learning_rate=0.3

You can see results of your job at http://127.0.0.1:8888

