import __builtin__
import traceback

'''
Module with tools for debugging.
Right now is purposed to
trace the file descriptor leaks
'''

openfiles = {}
oldfile = __builtin__.file


class newfile(oldfile):
    def __init__(self, *args):
        self.x = args[0]
        print "### OPENING %s ###" % str(self.x)
        oldfile.__init__(self, *args)
        __builtin__.file = oldfile
        __builtin__.open = oldopen
        openfiles[self] = traceback.format_stack()
        __builtin__.file = newfile
        __builtin__.open = newopen

    def close(self):
        print "### CLOSING %s ###" % str(self.x)
        oldfile.close(self)
        del openfiles[self]


oldopen = __builtin__.open


def newopen(*args, **kwargs):
    return newfile(*args)


__builtin__.file = newfile
__builtin__.open = newopen


def printOpenFiles():
    print "### OPEN FILES: ###"
    for f, tb in openfiles.iteritems():
        print(f.x)
        for stackel in tb:
            print(stackel)
