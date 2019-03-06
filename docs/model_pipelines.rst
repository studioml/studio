Trained model pipelines
=======================

Both Keras and TensorFlow handle data that has been packaged into
tensors gracefully. However, real-world data is often not properly formatted,
especially at the time of prediction. It may come as a 
collection (a list, set, or generator) of urls, have non-numeric
metadata that needs to be converted into tensor format, etc. Some of
the data may actually be missing or cause exceptions in preprocessing /
prediction stages.

Keras provides some features for image preprocessing to address this issue, and
TensorFlow has functions to include non-tensor values into the
computational graph. Both approaches have limitations - neither of them
can handle missing data while retaining performance. As a concrete example, let us consider the following 
(which is a basis of the unit test ``ModelPipeTest.test_model_pipe_mnist_urls`` in
`studio/tests/model\_util\_test.py <../studio/tests/model_util_test.py>`__):

We are training a network to classify mnist digits, and then trying to
predict images from urls. The simplest way to achieve this would be:
::

    from PIL import Image
    from io import BytesIO
    import urlllib
    import numpy as np

    from studio import model_util

    # setup and train keras model
    # 
    # urls is a list of urls

    labels = []
    for url in urls:
        data = urllib.urlopen(url).read()
        img = Image.open(BytesIO(data))
        
        # resize image to model input, and convert to tensor:
        img_t = model_util.resize_to_model_input(model)(img)

        labels.append(np.argmax(model.predict(img_t)))

The function ``model_util.resize_to_model_input(model)`` is used for
brevity and performes conversion of an image into a tensor with values
between 0 and 1, and shaped accoring to model input size. ``np.argmax``
in the last line is used to convert output class probablilities into the
class label.

Ok, so why do we need anything else? The code
above has two problems: 1) it does not handle exceptions (though that is
easy to fix) and 2) it processes the data sequentially. To address 2, we
could have spawned a bunch of child processes, and if the model is
evaluated on a CPU that probably would have been ok. But modern neural
networks get a substantial speed boost from using GPUs that don't do
well with hundreds of processes trying to run different instructions. 
To leverage GPU speedup, we'll need to create batches of data and
feed them to the GPU (preferrably in parallel with urls being fetched).

Keras offers a built in mechanism to do this:
``keras.models.predict_generator``. The relevant part of the code above
can then become:

::

    labels = []
    batch_size = 32
    tensor_generator = (model_util.resize_to_model_input(model)(Image.open(BytesIO(urllib.urlopen(url).read()))) for url in urls)
    output = model.predict_generator(tensor_generator, batch_size = batch_size, num_workers=4, no_batches = len(urls) / batch_size)

    for out_t in output:
        labels = np.stack(labels, np.argmax(out_t, axis=1))

We are handling de-batching implicitly when doing stacking of the labels
from different batches. This code will spin up 4 workers that will read
from the ``tensor_generator`` and prepare the next batch in the background
at the same time as the heavy lifting of prediction is handled by GPU.
So is that good enough? Not really. Rememeber our problem 1) - what
if there is an exception in the pre-processing / url is missing etc? By
default the entire script will come to a halt at that point. We could
filter out the missing urls by passing an exception-handling function
into the generator, but filtering out bad values will ruin the mapping
from url to label, rendering values after exception just as useless as
if the script were to stop.

The least ugly solution using Keras is to add another
input to the model, so that model applies to a key:tensor value; and
then after prediction sort out which ones were successfull. But this
process really doesn't have to be that complicated.

Studio provides primitives that make this job (that is
conceptually very simple) simple in code; and similar in usage to Keras.
The code above becomes (see unit test
``ModelPipeTest.test_model_pipe_mnist_urls`` in
``studio/tests/model_util_test.py``)

::

    pipe = model_util.ModelPipe()
    pipe.add(lambda url: urllib.urlopen(url).read(), num_workers=4, timeout=5)
    pipe.add(lambda img: Image.open(BytesIO(img)))
    pipe.add(model_util.resize_to_model_input(model))
    pipe.add(lambda x: 1-x)                                             
    pipe.add(model, num_workers=1, batch_size=32, batcher=np.vstack)
    pipe.add(lambda x: np.argmax(x, axis=1))

    output_dict = pipe({url:url for url in urls})

This runs the preprocessing logic (getting the url, converting it to 
an image, resizing the image, and convering to a tensor) using 4 workers that populate the
queue. The prediction is run using 1 worker with batch size 32 using the
same queue as input. Conversion of class probabilities to class labels
is also now a part of the model pipeline. In this example the input is a
dictionary mapping url to url. The functions will be applied only to the
values, so the output will become url: label. The pipeline can also be
applied to lists, generators and sets, in which case it returns the same
type of collection (if the input was list, it returns list etc) with
tuples (index, label) If any step of the preprocessing raises an
exception, it is caught, and corresponding output is filtered out. We are using
additional function ``lambda x: 1-x`` because in the mnist dataset the
digits are white on black background, whereas in the test urls digits
are black on white background.

The timeout parameter controls how long the workers wait if the queue is
empty (e.g. when urls take too long to fetch). Note that this also means
that the call ``pipe()`` will not return for a number of seconds specified
by the last (closest to output) timeout value.

Note that ``pipe.add()`` calls that don't specify a number of workers,
timeout, batch\_size, or batcher (function to assemble list of values
into a batch digestable by a function that operates on batches) are
composed with the function in previous calls to ``pipe.add()`` directly,
so that there is no unnecessary queues / buffers / workers.

Benchmark
---------

For a benchmark, we use
`StyleNet <http://ieeexplore.ieee.org/document/7780408/>`__ inference on
a dataset of 7k urls, some of which are missing / broken. The benchmark
is being run using EC2 p2.xlarge instances (with nVidia Tesla K80 gpus).
The one-by-one experiment is running inference one image at a time, pipe is
using model pipe primitives as described above. Batch size is number of
images being processed as a single call to ``model.predict``, and
``workers`` is number of prefetching workers

+--------------------------------+------------+--------------------+
| Experiment                     | Time (s)   | Time per url (s)   |
+================================+============+====================+
| One-by-one                     | 6994       | ~ 0.98             |
+--------------------------------+------------+--------------------+
| Pipe (batch 64, workers 4)     | 1581       | ~ 0.22             |
+--------------------------------+------------+--------------------+
| Pipe (batch 128, workers 32)   | 157        | ~ 0.02             |
+--------------------------------+------------+--------------------+
