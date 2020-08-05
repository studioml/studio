import tensorflow as tf

a = tf.constant([1.0, 5.0])

@tf.function
def forward(x):
  return x + 1.0

result = forward(a)
assert len(result) == 2

print("[ {} {} ]".format(result[0], result[1]))
