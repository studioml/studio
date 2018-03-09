import os
import pickle
from studio import fs_tracker


def clientFunction(args, files):
    print('client function call with args ' +
          str(args) + ' and files ' + str(files))

    modelfile = 'model.dat'
    filename = files.get('model') or \
        os.path.join(fs_tracker.get_artifact('modeldir'), modelfile)

    print("Trying to load file {}".format(filename))

    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            args = pickle.loads(f.read()) + 1

    else:
        print("Trying to write file {}".format(filename))
        with open(filename, 'wb') as f:
            f.write(pickle.dumps(args, protocol=2))

    return args


if __name__ == "__main__":
    clientFunction('test', {})
