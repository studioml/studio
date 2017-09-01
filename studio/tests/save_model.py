from keras.layers import Dense
from keras.models import Sequential

from studio import fs_tracker
import os

model = Sequential()
model.add(Dense(2, input_shape=(2,)))

weights = model.get_weights()
new_weights = []
for weight in weights:
  new_wights.append(weight + 1)

model.set_weights(new_weights)
model.save(os.path.join(fs_tracker.get_model_directory(), 'weights.h5'))
