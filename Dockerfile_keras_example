FROM ubuntu:16.04

MAINTAINER jiamingjxu@gmail.com

ENV LANG C.UTF-8

RUN mkdir -p /setupTesting

COPY . /setupTesting

WORKDIR /setupTesting

RUN apt-get update && \
	apt-get install -y python-pip libpq-dev python-dev && \
	apt-get install -y git && \
	pip install -U pytest && \
	pip install -r test_requirements.txt && \
	python setup.py build && \
	python setup.py install
	
CMD studio run --lifetime=30m --max-duration=20m --gpus 4 --queue=rmq_kmutch --force-git /examples/keras/train_mnist_keras.py