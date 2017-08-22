Cloud computing for studio
==========================

TensorFlow studio can be configured to submit jobs to the cloud. Right
now, only google cloud is supported (CPU only), as well as Amazon EC2
(CPU and GPU) Specifically, once configured (see
`here <gcloud_setup.md>`__ for configuration instructions for Google
Cloud, and `here <ec2_setup.md>`__ for EC2) command line

::

    studio run --cloud={gcloud|ec2|gcspot|ec2spot} my_script.py 

will create a instance, set up the python environment, run
``my_script.py``, and shutdown the instance. You'll be able to see the
progress of the job in studio ui. Different experiments might require
different hardware. Fortunately, google cloud offers flexibility of
instance configuration, and Amazon EC2 offers a variety of instances to
select from; TensorFlow Studio can leverage either. To specify number of
cpus or gpus needed, use flags --cpus and --gpus respectively. That is,
command line:

::

    studio run --cloud={gcloud|ec2|gcspot|ec2spot} --cpus=8 --gpus=1 my_script.py 

| will create an instance with 8 cpus and 1 gpu. The top of the line gpu
  in Amazon EC2 is Tesla K80 at the moment, and that's the only one
  available through tfstudio; we might provide some gpu selection flags
  in the future as well.
| The amount of ram and hard drive space can be configured via --ram /
  --hdd flags (using standard suffixes like g(G,Gb,GiB), m(M,MiB)). Note
  that the amount of RAM will be rounded up to a next factor of 256 Mb.
  Also note that for now extended RAM for google cloud is not supported,
  which means amount of RAM per CPU should be between 1 and 6 Gb. For
  Amazon EC2, studio will find the cheapest instances with higher specs
  than required; or throw an exception for too extravagant of a request.

Running on EC2 spot instances
-----------------------------

Basics
~~~~~~

Amazon EC2 offers so-called spot instances that are provided with a
substantial discount with the assumption that they can be removed from
the user at any moment. Google Compute Engine has similar product called
pre-emptible instances, but tfstudio does not support it just yet. In
short, for spot instances user specifies max price to pay for the
instance-hour. As long as the instance-hour price is below the specified
limit (bid), user is paying current price and uses the instance.
Otherwise, the instance shuts down and is being given to the higher
bidder. For more detailed explanation, refer to spot instnces user guide
https://aws.amazon.com/ec2/spot/. As you might have already guessed,
when running with ``--cloud=ec2spot`` option, the job is submitted to
the spot instances. You can additionally specify how much are you
willing to pay for instance via ``--bid=<bid_in_usd>`` or
``--bid=<percent_of_ondemand_price>%``. The latter format specifies bid
in percents of on-demand price. Unless you feel very generously towards
Amazon, there is no reason to specify price above 100% the on-demand
price (in fact, spot instance user guide discourages users from doing
so).

Note that bid is max price for *one* instance; number of instances will
vary (see below)

Autoscaling and number of instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given ephemeral nature of the spot workers, we need additional mechanism
controlling / balancing number of such instances. This mechanism is
called auto-scaling, and in the simplest setting it tries to keep number
of running instances constant. TF Studio handles downsize of the
auto-scaling groups when some workers are done and there is no work left
in the queue. You can specify this behaviour by setting
``--num-workers`` flag. Autoscaling allows more complex behaviour, such
as spinning extra machines if there are too many messages in the queue.
Default behaviour of studio is as follows - to start start with one spot
worker, and scale up when number of outstanding work messages in the
queue is above 0.

Running on Google Cloud spot (preemptible) instances
----------------------------------------------------

Google Cloud analog of EC2 spot instances is called preemtible
instances. Preemtible instances are similar to EC2 spot instances in the
fact that they are much cheaper than regular (on-demand) ones; and that
they can be taken away at any moment with very little or no notice. They
are different from EC2 spot instances in the bidding / market system -
the prices on preemptible instances are fixed and depend only on
hardware configuration. Thus, ``--bid`` has no effect when running with
``--cloud=gcspot``. Also, autoscaling on a queue for google cloud is in
an alpha stage and has some serious limitations; as such, we do not
support that just yet. The required number of workers has to be
specified via ``--num-workers`` (default is 1), and google group will
try to keep it constant (that is, if the instances are taken away, it
will try to take to spin up their replacements). When instances run out
of work, they automatically spin down and eventially delete the instance
group.
