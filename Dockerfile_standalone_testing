FROM ubuntu:16.04

MAINTAINER jiamingjxu@gmail.com

ENV LANG C.UTF-8

RUN mkdir -p /setupTesting

COPY . /setupTesting

WORKDIR /setupTesting

RUN apt-get update && apt-get install -y \
curl

RUN \
    apt-get update && apt-get install -y apt-transport-https && \
    curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" | tee -a /etc/apt/sources.list.d/kubernetes.list && \
    apt-get update && \
    apt-get install -y kubectl

RUN apt-get update && \
	apt-get install -y python-pip libpq-dev python-dev && \
	apt-get install -y git && \
	pip install -U pytest && \
	pip install -r test_requirements.txt && \
	python setup.py build && \
	python setup.py install
	
CMD python -m pytest tests/util_test.py
