from keras.layers import Dense
from keras.models import Sequential

from studio import fs_tracker
import numpy as np
import os

model = Sequential()
model.add(Dense(2, input_shape=(2,)))

model.set_weights([[[2,0],[0,2]]])
model.save(os.path.join(fs_tracker.get_model_directory(), 'weights.h5'))


