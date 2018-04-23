Cloud agnostic computing
========================

Users of StudioML who wish to make use of private infrastructure have
the option to either attach to message queues hosted by cloud vendors
or to make use of local queues.

A third option exists that makes use of privately hosted message queues 
and also privately hosted S3 storage.  In order to support this deployment
style StudioML can support the use of the RabbitMQ open source offering
from Pivotal.  When deployed in conjunction with Kubernetes and the 
Minio Private Cloud Storage server users of StudioML are freed to
implement a solution that has as much or as little security asthey require.

This document describes the use of RabbitMQ support with StudioML, and also
describes how a Kubernetes, and Minio based deployment can be achieved.

Running using RabbitMQ
----------------------

::

    cloud:
        queue:
                uri: "amqp://guest@guest@localhost:15672/"

RabbitMQ can be installed using the instructions found at
https://www.rabbitmq.com/install-debian.html.  It should be noted that 
this software relies on the Erlang runtime which should be installed first
anf for which instructions can also be found on the same web page at
https://www.rabbitmq.com/install-debian.html#erlang-requirementes

Local Deployment
~~~~~~~~~~~~~~~~

If you are installing RabiitMQ on a local environment you might find the 
management tools for it quite useful.  These can be installed using instructions
that can be found at https://www.rabbitmq.com/management.html.

::

    rabbitmq-plugins enable rabbitmq_management

Reference Deployment
~~~~~~~~~~~~~~~~~~~~

Kubernetes helm relationship.

Running using Kubernetes
------------------------

acs-engine, kops

Helm

Running using Minio
-------------------

Kubernetes persistent volume storage backend.

