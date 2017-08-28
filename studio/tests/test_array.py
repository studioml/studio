from studio import fs_tracker
import numpy as np


lr = np.load(fs_tracker.get_artifact('lr'))

print "fitness: %s" % np.abs(np.sum(lr))
