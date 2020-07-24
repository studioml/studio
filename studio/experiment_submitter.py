import json
import time
import traceback

from .unencrypted_payload_builder import UnencryptedPayloadBuilder
from .encrypted_payload_builder import EncryptedPayloadBuilder
from . import model

def submit_experiments(
        experiments,
        config=None,
        logger=None,
        queue=None,
        python_pkg=[]):

    num_experiments = len(experiments)

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

    # Update Python environment info for our experiments:
    for experiment in experiments:
        experiment.pythonenv = model.add_packages(experiment.pythonenv, python_pkg)

    # Reset our model setup, which will guarantee
    # that we rebuild our database and storage provider objects
    # that's important in the case that previous experiment batch
    # cleaned up after itself.
    model.reset_model_providers()

    # Now add them to experiments database:
    try:
        with model.get_db_provider(config) as db:
            for experiment in experiments:
                db.add_experiment(experiment)
    except BaseException:
        traceback.print_exc()
        raise

    for experiment in experiments:
        payload = payload_builder.construct(experiment, config, python_pkg)

        logger.debug("Submitting experiment: {0}"
                     .format(json.dumps(payload, indent=4)))

        queue.enqueue(json.dumps(payload))
        logger.info("studio run: submitted experiment " + experiment.key)

    logger.info("Added {0} experiment(s) in {1} seconds to queue {2}"
                .format(num_experiments, int(time.time() - start_time), queue.get_name()))
    return queue.get_name()


