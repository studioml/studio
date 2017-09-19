Cloud computing
===============

Studio can be configured to submit jobs to the cloud. Right
now, only Google Cloud is supported (CPU only), as well as Amazon EC2
(CPU and GPU). 
Once configured (see configuration instructions for `Google
Cloud <http://docs.studio.ml/en/latest/gcloud_setup.html>`__, and
`Amazon AWS <http://docs.studio.ml/en/latest/ec2_setup.html>`__) the command

::

    studio run --cloud={gcloud|ec2|gcspot|ec2spot} my_script.py 

will create an instance, set up the python environment, run
``my_script.py``, and shutdown the instance. You'll be able to see the
progress of the job in ``studio ui``. Different experiments might require
different hardware. Fortunately, Google Cloud offers flexibility of
instance configuration, and Amazon EC2 offers a variety of instances to
select from; Studio can leverage either. To specify the number of
cpus or gpus needed, use flags ``--cpus`` and ``--gpus`` respectively. That is,
the command:
::

    studio run --cloud={gcloud|ec2|gcspot|ec2spot} --cpus=8 --gpus=1 my_script.py 

will create an instance with 8 cpus and 1 gpu. The top of the line gpu
in Amazon EC2 is Tesla K80 at the moment, and that's the only one
available through Studio; we might provide some gpu selection flags
in the future as well.
  
The amount of ram and hard drive space can be configured via the 
``--ram`` / ``--hdd`` flags (using standard suffixes like g(G,Gb,GiB), m(M,MiB)). 
Note that the amount of RAM will be rounded up to the next factor of 256 Mb. 
Also note that for now extended RAM for Google Cloud is not supported, 
which means the amount of RAM per CPU should be between 1 and 6 Gb. 
For Amazon EC2, Studio will find the cheapest instances with higher specs than required, 
or throw an exception for too extravagant of a request.

Running on EC2 spot instances
-----------------------------

Basics
~~~~~~

Amazon EC2 offers so-called spot instances that are provided with a
substantial discount with the assumption that they can be taken from
the user at any moment. Google Compute Engine has a similar product called
preemptible instances, but Studio does not support it just yet. In
short, for spot instances the user specifies the max price to pay per
instance-hour. As long as the instance-hour price is below the specified
limit (bid), the user is pays the current price and uses the instance.
Otherwise, the instance shuts down and is given to the higher
bidder. For a more detailed explanation, refer to the spot instances user guide
https://aws.amazon.com/ec2/spot/. 

As you might have guessed,
when running with the ``--cloud=ec2spot`` option the job is submitted to
spot instances. You can additionally specify how much are you
willing to pay for these instances via ``--bid=<bid_in_usd>`` or
``--bid=<percent_of_ondemand_price>%``. The latter format specifies bid
in percent of on-demand price. Unless you feel very generous towards
Amazon there is no reason to specify a price above 100% the on-demand
price (in fact, the spot instance user guide discourages users from doing
so).

Note that bid is the max price for *one* instance; number of instances will
vary (see below).

Autoscaling and number of instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given the ephemeral nature of spot workers, we need an additional mechanism
controlling / balancing number of such instances. This mechanism is
called auto-scaling, and in the simplest setting it tries to keep number
of running instances constant. Studio handles downsizing of the
auto-scaling groups when some workers are done and there is no work left
in the queue. You can specify this behaviour by setting the
``--num-workers`` flag. 

Autoscaling allows more complex behaviour, such
as spinning up extra machines if there are too many messages in the queue.
The default behaviour of Studio is as follows - start start with one spot
worker, and scale up when the number of outstanding work messages in the
queue is above 0.

Running on Google Cloud spot (preemptible) instances
----------------------------------------------------

Google Cloud's analog of EC2 spot instances are called `preemptible
instances <https://cloud.google.com/preemptible-vms/>`__. 
Preemptible instances are similar to EC2 spot instances in that
they are much cheaper than regular (on-demand) instances and that
they can be taken away at any moment with very little or no notice. They
are different from EC2 spot instances in the bidding / market system -
the prices on preemptible instances are fixed and depend only on
hardware configuration. Thus, ``--bid`` has no effect when running with
``--cloud=gcspot``. 

Also, autoscaling on a queue for Google Cloud is in
an alpha state and has some serious limitations; as such, we do not
support it just yet. The required number of workers has to be
specified via ``--num-workers`` (the default is 1), and Google group will
try to keep it constant (that is, if the instances are taken away, it
will try to spin up their replacements). When instances run out
of work, they automatically spin down and eventually the instance group is deleted.
