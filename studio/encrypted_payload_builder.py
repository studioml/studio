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
    def __init__(self, name: str,
                 receiver_keypath: str,
                 sender_keypath: str = None):
        """
        param: name - payload builder name
        param: receiver_keypath - file path to .pem file
                                  with recipient public key
        param: sender_keypath - file path to .pem file
                                  with sender private key
        """
        super(EncryptedPayloadBuilder, self).__init__(name)

        # XXX Set logger verbosity level here
        self.logger = logs.getLogger(self.__class__.__name__)

        self.recipient_key_path = receiver_keypath
        self.recipient_key = None
        try:
            self.recipient_key =\
                RSA.import_key(open(self.recipient_key_path).read())
        except:
            msg = "FAILED to import recipient public key from: {0}"\
                .format(self.recipient_key_path)
            self.logger.error(msg)
            raise ValueError(msg)

        self.sender_key_path = sender_keypath
        self.sender_key = None
        self.sender_fingerprint = None
        if self.sender_key_path:
            key_text = None
            try:
                with open(self.sender_key_path, 'r') as keyfile:
                    key_text = keyfile.read()
            except:
                msg = "FAILED to open/read sender private key file: {0}"\
                    .format(self.sender_key_path)
                self.logger.error(msg)
                raise ValueError(msg)

            try:
                self.sender_key = RSA.import_key(key_text)
            except:
                msg = "FAILED to import sender private key from: {0}"\
                    .format(self.sender_key_path)
                self.logger.error(msg)
                raise ValueError(msg)

            self.sender_fingerprint =\
                SHA256.new(key_text.encode("utf-8")).digest()
            self.sender_fingerprint = \
                base64.b64encode(self.sender_fingerprint).decode("utf-8")

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

    def _rsa_encrypt_data_to_base64(self, key, data):
        # Encrypt byte data with RSA key
        cipher_rsa = PKCS1_OAEP.new(key=key, hashAlgo=SHA256)
        encrypted_data = cipher_rsa.encrypt(data)
        encrypted_data_base64 = base64.b64encode(encrypted_data)
        return encrypted_data_base64

    def _encrypt_str(self, workload: str):
        # Generate one-time symmetric session key:
        session_key = nacl.utils.random(32)

        # Encrypt the data with the NaCL session key
        data_to_encrypt = workload.encode("utf-8")
        box_out = nacl.secret.SecretBox(session_key)
        encrypted_data = box_out.encrypt(data_to_encrypt)
        encrypted_data_text = base64.b64encode(encrypted_data)

        # Encrypt the session key with the public RSA key
        encrypted_session_key_text =\
            self._rsa_encrypt_data_to_base64(self.recipient_key, session_key)

        return encrypted_session_key_text, encrypted_data_text

    def _get_signature_str(self, workload: str):
        data_to_hash = workload.encode("utf-8")
        data_hash = SHA256.new(data_to_hash).digest()
        encrypted_data_hash =\
            self._rsa_encrypt_data_to_base64(self.sender_key, data_hash)
        return encrypted_data_hash

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
        unencrypted_payload_str = json.dumps(unencrypted_payload)

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
        enc_key, enc_payload = self._encrypt_str(unencrypted_payload_str)

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
        if self.sender_key is not None:
            # Generate sender/workload signature:
            signature_str = self._get_signature_str(unencrypted_payload_str)
            encrypted_payload["message"]["signature"] =\
                "{0}".format(signature_str.decode("utf-8"))
            encrypted_payload["message"]["fingerprint"] =\
                "{0}".format(self.sender_fingerprint)

        return encrypted_payload

