import json
import os
import time
import traceback

from studio.artifacts.artifact import Artifact
from studio.db_providers import db_provider_setup
from studio.experiments.experiment import Experiment
from studio import git_util
from studio.payload_builders.payload_builder import PayloadBuilder
from studio.payload_builders.unencrypted_payload_builder import UnencryptedPayloadBuilder
from studio.encrypted_payload_builder import EncryptedPayloadBuilder
from studio.storage import storage_setup
from studio.util import util

def submit_experiments(
        experiments,
        config=None,
        logger=None,
        queue=None,
        python_pkg=[],
        external_payload_builder: PayloadBuilder=None):

    num_experiments = len(experiments)

    payload_builder = external_payload_builder
    if payload_builder is None:
        # Setup our own payload builder
        payload_builder = UnencryptedPayloadBuilder("simple-payload")
        # Are we using experiment payload encryption?
        public_key_path = config.get('public_key_path', None)
        if public_key_path is not None:
            logger.info("Using RSA public key path: {0}".format(public_key_path))
            signing_key_path = config.get('signing_key_path', None)
            if signing_key_path is not None:
                logger.info("Using RSA signing key path: {0}".format(signing_key_path))
            payload_builder = \
                EncryptedPayloadBuilder(
                    "cs-rsa-encryptor [{0}]".format(public_key_path),
                    public_key_path, signing_key_path)

    start_time = time.time()

    # Reset our storage setup, which will guarantee
    # that we rebuild our database and storage provider objects
    # that's important in the case that previous experiment batch
    # cleaned up after itself.
    storage_setup.reset_storage()

    for experiment in experiments:
        # Update Python environment info for our experiments:
        experiment.pythonenv = util.add_packages(experiment.pythonenv, python_pkg)

        # Add experiment to database:
        try:
            with db_provider_setup.get_db_provider(config) as db:
                _add_git_info(experiment, logger)
                db.add_experiment(experiment)
        except BaseException:
            traceback.print_exc()
            raise

        payload = payload_builder.construct(experiment, config, python_pkg)

        logger.info("Submitting experiment: {0}"
                     .format(json.dumps(payload, indent=4)))

        queue.enqueue(json.dumps(payload))
        logger.info("studio run: submitted experiment " + experiment.key)

    logger.info("Added {0} experiment(s) in {1} seconds to queue {2}"
                .format(num_experiments, int(time.time() - start_time), queue.get_name()))
    return queue.get_name()

def _add_git_info(experiment: Experiment, logger):
    wrk_space: Artifact = experiment.artifacts.get('workspace', None)
    if wrk_space is not None:
        if wrk_space.local_path is not None and \
                os.path.exists(wrk_space.local_path):
            if logger is not None:
                logger.info("git location for experiment %s", wrk_space.local_path)
            experiment.git = git_util.get_git_info(wrk_space.local_path)
