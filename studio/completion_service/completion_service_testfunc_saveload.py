import os
import pickle
from studio import fs_tracker


def clientFunction(args, files):
    print('client function call with args ' +
          str(args) + ' and files ' + str(files))

    modelfile = 'model.dat'
    if args:
        filename = os.path.join(fs_tracker.get_artifact('modeldir'), modelfile)
        with open(filename, 'wb') as f:
            f.write(pickle.dumps(args, protocol=2))

        return args

    else:
        filename = files['model']
        with open(filename, 'rb') as f:
            args = pickle.loads(f.read())

        return args


if __name__ == "__main__":
    clientFunction('test', {})
