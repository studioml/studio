============================
Serving models with Studio.ML
============================

Once the model is trained, it is a frequent task to make it available as a service.
This is usually a tedious task because of two reasons: 

 - It requires certain DevOps knowledge, configuration
   of firewalls and ports on the instance etc. 

 - Trained models need some extra pre/post processing 
   steps or data fetching steps (this happens when interaction with 
   the data is different at the training and inference stage, which
   is pretty much always)

Studio.ML can execute entire process of serving a model from a single 
command (which mainly caters to the first bullet point). It also provides
simple and powerful primitives for pre / post processing with 
arbitrary python code. 

Basics
------
The basic command for serving is 

::

    studio serve <experiment_key> 


where `<experiment_key>` is a key of the experiment responsible for training models. 
This command takes the same cloud execution arguments as `studio run`, which 
means that serving a model on a EC2 instance with a GPU is as simple as adding 
`--cloud=ec2 --gpus=1` flags. 
To figure out which model to serve, `studio serve` fetches the artifact `modeldir` of the experiment. 
By default (as of now, only Keras models are supported by default), it `studio serve` takes the last
training checkpoint. Served model expects POST request with data being dictionary of the form 

::

    {key1: <pickled numpy array1>, key2: <pickled numpy array2>, ...}

and returns the dictionary of the form

::

    {key1: <pickled inference result1, key2: <pickled inference result2>, ...}


The pickling is necessary because numpy arrays are not JSON serializable. 
If no checkpoints are found, an identity model is served (i.e. the model that returns its input)

Wrappers for pre/post processing 
--------------------------------
To customize our model (for instance, if we want to pass image urls as an input, and model
needs to fetch the image data before inference), can specify a model wrapper. 
A model wrapper is a python file or module that has function `create_model()`
This function takes path to a directory with experiment checkpoints and returns
a python function converting dictionary to dictionary. 
As a concrete example (see `<../studio/tests/model_increment.py>`), the following snippet 
is a wrapper that ignores experiment checkpoints and returns a model that increments inputs 
by 1:

::

     import six 

     def create_model(modeldir):
        def model(data):
            retval = {}
            for k, v in six.iteritems(data):
                retval[k] = v + 1 
            return retval

        return model       
            



Wrappers play nicely with model pipelines provided by Studio.ML `<docs/model_pipelines.rst>`. For example, the following code is a wrapper
that downloads the urls in multiple threads, and batched prediction:

::

    import glob
    from studio import model_util

    def create_model(modeldir):
            
        # load latest keras model
        hdf5_files = [
        (p, os.path.getmtime(p))
        for p in
        glob.glob(modeldir + '/*.hdf*')]
    
        last_checkpoint = max(hdf5_files, key=lambda t: t[1])[0]
        keras_model = keras.models.load_model(last_checkpoint)
        
        # create model pipe
        pipe = model_util.ModelPipe()
        pipe.add(lambda url: urllib.urlopen(url).read(), num_workers=4, timeout=5)
        pipe.add(lambda img: Image.open(BytesIO(img)))
        pipe.add(model_util.resize_to_model_input(model))
        pipe.add(model, num_workers=1, batch_size=32, batcher=np.vstack)
        
        return pipe


Command-line options
--------------------

  - `--wrapper` specifies a python script with `create_model` function that generates the model to be served
     (see above)

  - `--port` specifies port on which the model will be served. For cloud instances this port is 
     automatically added into the firewall rules

  - `--killafter` by default, the model serving shuts down after an hour of inactivity. Use this option to
     modify inactive (no requests) time after which the server shuts down. 

  - `--host` can be either `0.0.0.0` - serve the model to the world, or `losthost` - serve internally (model will only
    be available from the same server)

 


