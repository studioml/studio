import numpy as np
import pickle
import os

no_samples = 100
dim_samples = 5

learning_rate = 0.01
no_steps = 10

X = np.random.random((no_samples, dim_samples))
y = np.random.random((no_samples,))

w = np.random.random((dim_samples,))

for step in range(no_steps):
    yhat = X.dot(w)
    err = (yhat - y)
    dw = err.dot(X)
    w -= learning_rate * dw
    loss = 0.5 * err.dot(err)

    print("step = {}, loss = {}, L2 norm = {}".format(step, loss, w.dot(w)))

#    with open(os.path.expanduser('~/weights/lr_w_{}_{}.pck'
#                                 .format(step, loss)), 'w') as f:
#        f.write(pickle.dumps(w))

    from studio import fs_tracker
    with open(os.path.join(fs_tracker.get_artifact('weights'),
                           'lr_w_{}_{}.pck'.format(step, loss)),
              'w') as f:
        f.write(pickle.dumps(w))
