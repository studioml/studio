Setting up Amazon EC2 
=====================

This page describes the process of configuring Studio to work
with Amazon EC2. We assume that you already have AWS credentials 
and an AWS account set up.

Install boto3
-------------

Studio interacts with AWS via the boto3 API. Thus, in order to use EC2
cloud you'll need to install boto3:

::

    pip install boto3

Set up credentials
------------------

Add credentials to a location where boto3 can access them. The
recommended way is to install the AWS CLI:

::

    pip install awscli

and then run

::

    aws configure

and enter your AWS credentials and region. The output format cam be left as
None. Alternatively, use any method of letting boto3 know the
credentials described here:
http://boto3.readthedocs.io/en/latest/guide/configuration.html
