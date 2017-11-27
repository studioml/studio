import glob
import os
from studio import fs_tracker
import pickle


weights_list = sorted(
    glob.glob(
        os.path.join(
            fs_tracker.get_artifact('w'),
            '*.pck')))

print('*****')
print(weights_list[-1])
with open(weights_list[-1], 'r') as f:
    w = pickle.load(f)

print(w.dot(w))
print('*****')
