import importlib
from studio import fs_tracker

def clientFunction(args):
    print 'client function call with args ' + str(args)
    return args

if __name__ == "__main__":
    clientFunction()
