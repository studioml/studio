Configuring tfstudio to work with Amazon EC2 cloud
==================================================

This page describes the process of setting configuring studio to work
with Amazon EC2 We assume that you have an AWS account set up already,
and AWS credentials.

Install boto3
-------------

tfstudio interacts with AWS via boto3 API. Thus, in order to use EC2
cloud, you'll need to install boto3:

::

    pip install boto3

Set up credentials
------------------

Add credentials to the location where boto3 can access them. The
recommended way is to install AWS CLI:

::

    pip install awscli

and then run

::

    aws configure

and enter AWS credentials and region. The output format cam be left as
None. Alternatively, use any method of letting boto3 know the
credentials described here:
http://boto3.readthedocs.io/en/latest/guide/configuration.html
