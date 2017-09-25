from studio import fs_tracker
import numpy as np

if fs_tracker.get_artifact('lr') is not None:
    lr = np.load(fs_tracker.get_artifact('lr'))
else:
    lr = np.random.random(10)

print("fitness: %s" % np.abs(np.sum(lr)))
