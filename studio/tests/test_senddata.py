from studio import fs_tracker
from studio import model

import subprocess
import os

db = model.get_db_provider()

experiment = model.create_experiment('test_readdata.py', [])

with open('aaa.txt', 'w') as f:
    f.write('bbb')

subprocess.call([
    'studio', 'run',
    '--experiment=' + experiment.key,
    '--force-git',
    '--capture-once=./aaa.txt:data',
    'test_readdata.py',
])
