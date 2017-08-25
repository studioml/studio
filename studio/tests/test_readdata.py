from studio import fs_tracker
import os


with open(fs_tracker.get_artifact('data')) as f:
    data = f.read()

print data
    
