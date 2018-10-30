Cloud agnostic deployment
=========================

StudioML contains two enduring places where data is stored, and tasks 
are queued.  For individual consumers of StudioML using cloud based 
resources to provision storage and queuing facilities is often the best
fit both costwise and complexity.  This iis appropriate when public datasets
are being used and when results do not have privacy or integrity issues
around their use.

In the case of instituational or commercial users of Machine Learning
these requirements are more strigent and could easily involve requirements
related to privacy by design, and data movement among many other concerns.
Other motivations related to cost can also lead users into on-premise 
or edge based computing.

StudioML does not directly address the requirements of legislation such
as GDPR or the data security requirements that users might have, but it
does offer the ability for users to deploy StudioML into environments 
that they choose to address these needs.

Users of StudioML who wish to make use of private infrastructure have
the option to selectively attach to message queues offered by cloud vendors
or to make use of local disk based queues.

StudioML additional option exists to make use of privately hosted 
RabbitMQ message queues and/or privately hosted Minio.io S3 storage.
When deployed in conjunction with Kubernetes users of StudioML are free to
implement a solution that has as much or as little security as they require.

This document describes the use of RabbitMQ support with StudioML, and also
describes how a Kubernetes, and Minio based deployment can be achieved.

Running RabbitMQ
----------------------------------

RabbitMQ (RMQ) can be installed using the instructions found at
https://www.rabbitmq.com/install-debian.html.  It should be noted that 
this software relies on the Erlang runtime which should be installed first
anf for which instructions can also be found on the same web page at
https://www.rabbitmq.com/install-debian.html#erlang-requirementes.

If you are hosting in the cloud then most cloud vendors have free
bitnami distributions of RabbitMQ available for smaller installations
that can be easily used.

RMQ can be deployed in many different contexts including :

* A standalone on-premise server
* A cloud compute instance
  - Microsoft VM template (Bitnami)
  - Amazon Marketplace AMI (Bitnami)
  - Google Cloud Platform Launcher as both container and VM images

The choice taken will largely depend upon your operational criteria.  In any event
once the installation has been completed you should ensure that the 5672, and 
15672 ports are open for access and that the user name and password you intend on
using with the StudioML client have been added.

If yopu intend on using the RMQ server for any period of time within a cloud
context it is a good idea to set the IP Address allocated to be static to ensure
that the machine remains at the same endpoint between reboots.

When running RabbitMQ care should be made to ensure that the log files being
generated do not fill your server and cause failures.  Adding the following
block to your RabbitMQ servers rabbitmq.config file will prevent this.

::
    {log, [
        {file, [{file, "/var/log/rabbitmq/rabbitmq.log"}, %% log.file
                {level, info},        %% log.file.info
                {date, "$D0"},           %% log.file.rotation.date
                {size, 1024},            %% log.file.rotation.size
                {count, 15}            %% log.file.rotation.count
        ]}
    ]},

It is also highly recommended that the number of concurrent connections be also limited
using the web administration interface.

The StudioML tools need to access the RMQ server using its management
interface.  The following example shows an example of accessing a RabbitMQ server
on a local host.  The user name password and the host name will also be used
by system to determine where queues identified in the 'studio run' command
are hosted.

The amqp URI used within the ~/.studioml/config.yaml file is used by the StudioML 
client to locate the queue server and to also specify some important options. The
following example shows the configuration for a rabbitMQ server running locally
to the studioML client.  The timeout values shown are critically important
when queuing work in a production environment as the timeouts that exist by default
inside the rabbitMQ libraries is too small to be viable in a distributed system.

::

    cloud:
        queue:
            rmq: "amqp://guest@password@localhost:15672/%2f?connection_attempts=30&retry_delay=.5&socket_timeout=5"

When running your experiment you should use a rmq\_ prefixed queue name and option
on the command line for the RabbitMQ parameters, for example:

studio run ... --queue=rmq_StudioML ...

Local Deployment
~~~~~~~~~~~~~~~~

If you are installing RabbitMQ on a local environment you might find the 
management tools for it quite useful.  These can be installed using instructions
that can be found at https://www.rabbitmq.com/management.html.

::

    rabbitmq-plugins enable rabbitmq_management

When deploying to the cloud using templates or launchers the management component
will in most cases be present already.

Running Minio
-------------

In order to make use of StudioML storage features within an on-premise environment
or within a cloud environment in a vendor neutral manner, minio can be used.  Minio
support the S3 v4 API and is 100% compatible with the S3 protocol.  If you are
using a cloud deployment the minio paid route can also be used as a shim above 
the storage tier that is cloud vendor specific, this applies to Azure for 
example allowing Azure blob stores to be reflected as S3 storage.

Minio can be deployed in many different configurations.  When starting out with 10's of
compute instances a standalone Minio deploy using Ubuntu 17.10 should easily handle the load,
https://docs.minio.io/docs/minio-quickstart-guide.

Using the manual install method will result in a binary that can be run manually using
a nohup style execution.  When run in this manner minio will generate a random access key
id and secret access key id which can be used for temporary deployments.  These options
are free but again will scale to clusters that done require large multi GB files
to be copied from your server.

Minio also scales up to large multi peta-byte (PB) sized for their paid offerings including
gateways to blob data stores.

If you do deploy minio in a default single machine installation manually
then the Minio console will output a generated AWS_ACCESS_KEY_ID, and
AWS_SECRET_ACCESS_KEY.  However, We recommend doing your own configuration.

To do this add a database and storage section to your experiments yaml configuration file
that points to a deployment of Minio and add the Access Key ID and Secret Access Key
to the file as follows:

	database:
		type: s3
		endpoint: http://41.11.110.221:9000/
		bucket: "studioml-meta"
		authentication: none

	storage:
		type: s3
		endpoint: http://41.11.110.221:9000/
		bucket: "kmutch-azure-minio"

	server:
		authentication: None

	env:
		AWS_ACCESS_KEY_ID: J27XQZC2IYBGXH56NO2
		AWS_DEFAULT_REGION: us-west-2
		AWS_SECRET_ACCESS_KEY: "zMohtbV2O+scofEyNgdxmPAdjQKrT+vfu1Uh23hm"
		PATH: "%PATH%:./bin"

When running the experiment ensure that the Minio specific AWS environment variables
are defined within your terminal session.

Then upon the initial run of the minio binary ensure that you define the AWS variables
as environment variables and these will be picked up as the values used by the server
for the default user.

