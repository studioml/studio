from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
import nacl.secret
import nacl.utils
import base64
import json

from .payload_builder import PayloadBuilder
from studio import logs
from .unencrypted_payload_builder import UnencryptedPayloadBuilder

class EncryptedPayloadBuilder(PayloadBuilder):
    """
    Implementation for experiment payload builder
    using public key RSA encryption.
    """
    def __init__(self, name: str, keypath: str):
        """
        param: name - payload builder name
        param: keypath - file path to .pem file with public key
        """
        super(EncryptedPayloadBuilder, self).__init__(name)

        # XXX Set logger verbosity level here
        self.logger = logs.getLogger(self.__class__.__name__)

        self.key_path = keypath
        self.recipient_key = None
        try:
            self.recipient_key = RSA.import_key(open(self.key_path).read())
        except:
            self.logger.error(
                "FAILED to import recipient public key from: {0}".format(self.key_path))
            return

        self.simple_builder =\
            UnencryptedPayloadBuilder("simple-builder-for-encryptor")

    def _import_rsa_key(self, key_path: str):
        key = None
        try:
            key = RSA.import_key(open(key_path).read())
        except:
            self.logger.error(
                "FAILED to import RSA key from: {0}".format(key_path))
            key = None
        return key

    def _encrypt_str(self, workload: str):
        # Generate one-time symmetric session key:
        session_key = nacl.utils.random(32)

        # Encrypt the data with the NaCL session key
        data_to_encrypt = workload.encode("utf-8")
        box_out = nacl.secret.SecretBox(session_key)
        encrypted_data = box_out.encrypt(data_to_encrypt)
        encrypted_data_text = base64.b64encode(encrypted_data)

        # Encrypt the session key with the public RSA key
        cipher_rsa = PKCS1_OAEP.new(key=self.recipient_key, hashAlgo=SHA256)
        encrypted_session_key = cipher_rsa.encrypt(session_key)
        encrypted_session_key_text = base64.b64encode(encrypted_session_key)

        return encrypted_session_key_text, encrypted_data_text

    def _decrypt_data(self, private_key_path, encrypted_key_text, encrypted_data_text):
        private_key = self._import_rsa_key(private_key_path)
        if private_key is None:
            return None

        try:
            private_key = RSA.import_key(open(private_key_path).read())
        except:
            self.logger.error(
                "FAILED to import private key from: {0}".format(private_key_path))
            return None

        # Decrypt the session key with the private RSA key
        cipher_rsa = PKCS1_OAEP.new(private_key)
        session_key = cipher_rsa.decrypt(
            base64.b64decode(encrypted_key_text))

        # Decrypt the data with the NaCL session key
        box_in = nacl.secret.SecretBox(session_key)
        decrypted_data = box_in.decrypt(
            base64.b64decode(encrypted_data_text))
        decrypted_data = decrypted_data.decode("utf-8")

        return decrypted_data

    def construct(self, experiment, config, packages):
        unencrypted_payload =\
            self.simple_builder.construct(experiment, config, packages)

        # Construct payload template:
        encrypted_payload = {
            "message": {
                "experiment": {
                    "status": "unknown",
                    "pythonver": "unknown",
                },
                "time_added": None,
                "experiment_lifetime": "unknown",
                "resources_needed": None,
                "payload": "None"
            }
        }

        # Now fill it up with experiment properties:
        enc_key, enc_payload = self._encrypt_str(json.dumps(unencrypted_payload))

        encrypted_payload["message"]["experiment"]["status"] =\
            experiment.status
        encrypted_payload["message"]["experiment"]["pythonver"] =\
            experiment.pythonver
        encrypted_payload["message"]["time_added"] =\
            experiment.time_added
        encrypted_payload["message"]["experiment_lifetime"] =\
            experiment.max_duration
        encrypted_payload["message"]["resources_needed"] =\
            experiment.resources_needed
        encrypted_payload["message"]["payload"] =\
            "{0},{1}".format(enc_key.decode("utf-8"), enc_payload.decode("utf-8"))

        return encrypted_payload

