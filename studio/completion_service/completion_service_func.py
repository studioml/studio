
def clientFunction(args, files):
    print('client function call with args ' +
          str(args) + ' and files ' + str(files))
    return args


if __name__ == "__main__":
    clientFunction()
