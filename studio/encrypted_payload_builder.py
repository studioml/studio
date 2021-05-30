from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
import nacl.secret
import nacl.utils
from nacl.signing import SigningKey, VerifyKey
import base64
import json
from sshpubkeys import SSHKey

from studio.ed25519_key_util import Ed25519KeyUtil
from studio.payload_builders.payload_builder import PayloadBuilder
from studio.util import logs
from studio.payload_builders.unencrypted_payload_builder import UnencryptedPayloadBuilder
from studio.util.util import check_for_kb_interrupt

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
        self.logger = logs.get_logger(self.__class__.__name__)

        self.recipient_key_path = receiver_keypath
        self.recipient_key = None
        try:
            self.recipient_key =\
                RSA.import_key(open(self.recipient_key_path).read())
        except:
            check_for_kb_interrupt()
            msg = "FAILED to import recipient public key from: {0}"\
                .format(self.recipient_key_path)
            self.logger.error(msg)
            raise ValueError(msg)

        self.sender_key_path = sender_keypath

        self.sender_key: SigningKey = None
        self.verify_key: VerifyKey = None
        self.sender_fingerprint = None

        if self.sender_key_path is None:
            self.logger.error("Signing key path must be specified for encrypted payloads. ABORTING.")
            raise ValueError()

        # We expect ed25519 signing key in "openssh private key" format
        try:
            public_key_data, private_key_data =\
                Ed25519KeyUtil.parse_private_key_file(
                    self.sender_key_path, self.logger)
            if public_key_data is None or private_key_data is None:
                self._raise_error(
                    "Failed to import private signing key from {0}. ABORTING."
                        .format(self.sender_key_path))

            self.sender_key = SigningKey(private_key_data)
            self.verify_key = VerifyKey(public_key_data)
        except Exception:
            self._raise_error("FAILED to open/read private signing key file: {0}"\
                .format(self.sender_key_path))

        self.sender_fingerprint = \
            self._get_fingerprint(public_key_data)

        self.simple_builder =\
            UnencryptedPayloadBuilder("simple-builder-for-encryptor")

    def _raise_error(self, msg: str):
        self.logger.error(msg)
        raise ValueError(msg)

    def _add_encoding(self, bytes_val):
        blen: int = len(bytes_val)
        return blen.to_bytes(4,'big') + bytes_val

    def _get_fingerprint(self, signing_key):
        # This is hard-coded for now, until we figure out
        # a way to do this properly:
        encoding = self._add_encoding(b'ssh-ed25519') +\
                   self._add_encoding(signing_key)

        ssh_key_text: str = base64.b64encode(encoding).decode("utf-8")
        ssh_key = SSHKey("ssh-ed25519 {0}"
                         .format(ssh_key_text))
        try:
            ssh_key.parse()
        except Exception:
            self._raise_error("INVALID signing key type. ABORTING.")

        return ssh_key.hash_sha256()  # SHA256:xyz

    def _import_rsa_key(self, key_path: str):
        key = None
        try:
            key = RSA.import_key(open(key_path).read())
        except:
            check_for_kb_interrupt()
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

    def _sign_payload(self, encrypted_payload):
        """
        encrypted_payload - base64 representation of the encrypted payload.
        returns: base64-encoded signature
        """
        sign_message = self.sender_key.sign(encrypted_payload)

        # Verify what we generated just in case:
        try:
            self.verify_key.verify(sign_message)
        except Exception as exc:
            msg: str = "FAILED to verify signed data - {0}. ABORTING."\
                .format(exc)
            self._raise_error(msg)

        result = base64.b64encode(sign_message.signature)
        return result

    def _decrypt_data(self, private_key_path, encrypted_key_text, encrypted_data_text):
        private_key = self._import_rsa_key(private_key_path)
        if private_key is None:
            return None

        try:
            private_key = RSA.import_key(open(private_key_path).read())
        except:
            check_for_kb_interrupt()
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
            final_payload = encrypted_payload["message"]["payload"]
            payload_signature = self._sign_payload(final_payload.encode("utf-8"))
            encrypted_payload["message"]["signature"] =\
                "{0}".format(payload_signature.decode("utf-8"))
            encrypted_payload["message"]["fingerprint"] =\
                "{0}".format(self.sender_fingerprint)

        #print(json.dumps(encrypted_payload, indent=4))

        return encrypted_payload

