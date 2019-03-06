from studio import fs_tracker
import numpy as np

try:
    lr = np.load(fs_tracker.get_artifact('lr'))
except BaseException:
    lr = np.random.random(10)

print("fitness: %s" % np.abs(np.sum(lr)))
