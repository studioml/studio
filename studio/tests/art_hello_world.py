import sys
from studio import fs_tracker

print(fs_tracker.get_artifact('f'))
with open(fs_tracker.get_artifact('f'), 'r') as f:
    print(f.read())

if len(sys.argv) > 1:
    with open(fs_tracker.get_artifact('f'), 'w') as f:
        f.write(sys.argv[1])


sys.stdout.flush()
