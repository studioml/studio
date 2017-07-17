# Setting up a remote worker
This page describes a procedure for setting up a remote worker for studio. Remote workers are listening to the queue; once a worker receives a message from the queue, it starts the experiments

## I. Getting credentials 
1. Remote workers work by listening to distributed queue. Right now the distributed queue is backed by Google PubSub; so to access it, you'll need application credentials from Google. (in the future, it may be implemented via firebase itself, in which case this step should become obsolete). If you made it this far, you are likely to have a google cloud compute account set up; but even if not, go to http://cloud.google.com and either set up an account or sign in. 
2. Next, create a project if you don't have a project corresponding to studio just yet. 
3. Then go to API Manager -> Credentials, and click "Create credentials" -> "Service account key"
4. Choose "New service account" from the "Select accout" dropdown,  and keep key type as JSON
5. Enter a name of your liking for account (google will convert it to a uniqie name), and choose "PubSub Editor" for a role (technically, you can create 2 keys, and keep publisher on a machine that submits work, and subscriber key on a machine that implements the work). If you are planning to use cloud workers, it is also recommended to add Compute Engine / Compute Engine Admin (v1). 

6. Save a json credentials file
7. Add `GOOGLE_APPLICATION_CREDENTIALS` variable to the environment that points to the saved json credentials file both on work submitter and work implementer. 

## II. Setting up remote worker
If you don't have your own docker container to run jobs in, follow the instructions below. Otherwise, jump to the next section. 
1. Install docker, and nvidia-docker to use gpus
2. Clone the repo

        git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e .
 
   To check success of installation, you can run `python $(which nosetests) --processes=10 --process-timeout=600` to run the tests (may take about 10 min to finish)

3. Start worker (queue name is a name of the queue that will define where submit work to)
    
        studio-start-remote-worker <queue-name>


## III. Setting up a remote worker in an existing docker container. 
This section applies to the cases when you already have a docker image/container, and would like studio remote worker to run in it (wink wink Antoine :)
Full disclosure - this is basically manual retrace of steps happening inside `Dockerfile` and `studio-start-remote-worker` script. As such, these steps can and should be automated, but the particular flavor of automation is left as an exercise for the reader. 

1. Within the docker container, install the prerequisites (if you don't have them already). Particular form of this command depends on your docker image, but if you made it this far, you can handle that. We'll assume you are using ubuntu image. If your host machine does not have gpus or nvidia cuda drivers, don't install tensorflow-gpu package.

        apt install -y python-dev python-pip git && pip install --upgrade pip && pip install tensorflow tensorflow-gpu

2. Within docker container, install studio:

        git clone https://github.com/ilblackdragon/studio && cd studio && pip install -e .

3. Make sure `GOOGLE_APPLICATION_CREDENTIALS` evironment variable is set up and pointing to the credentials file inside the docker container. You can either copy or mount the file, and set up the variable accordingly.

4. Start remote worker script:

        studio-remote-worker --queue <queue_name> 
    
If you want the worker to quit after a single experiment (e.g. if you are using fresh docker container for each experiment), add an extra flag `--single-run` to the studio-remote-worker command line. Otherwise, the remote worker will try to execute all outstanding tasks in the queue and quit after that. 

## IV. Submitting work
On a submitting machine (usually local):

    studio-runner --queue <queue-name> <any_other_args> script.py <script_args>

This script should quit promptly, but you'll be able to see experiment progress in studio web ui 
