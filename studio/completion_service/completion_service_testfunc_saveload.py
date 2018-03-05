from studio import fs_tracker


def clientFunction(args, files):
    print('client function call with args ' +
          str(args) + ' and files ' + str(files))

    modelfile = 'model.dat'
    if args:
        filename = os.path.join(fs_tracker.get_artifact('modeldir'), modelfile)
        with open(filename, 'w') as f:
            f.write(pickle.dumps(args))

        return args

    else:
        with open(files['model']) as f:
            args = pickle.load(f)

        return args


if __name__ == "__main__":
    clientFunction()
