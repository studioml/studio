import sys
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import nacl.secret
import nacl.utils
import base64

class Encryptor:
    """
    Implementation for experiment payload builder
    using public key RSA encryption.
    """
    def __init__(self, keypath: str):
        """
        param: keypath - file path to .pem file with public key
        """

        self.key_path = keypath
        self.recipient_key = None
        try:
            self.recipient_key = RSA.import_key(open(self.key_path).read())
        except:
            print(
                "FAILED to import recipient public key from: {0}".format(self.key_path))
            return

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
        cipher_rsa = PKCS1_OAEP.new(self.recipient_key)
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

    def encrypt(self, payload: str):
        enc_key, enc_payload = self._encrypt_str(payload)

        enc_key_str = enc_key.decode("utf-8")
        enc_payload_str = enc_payload.decode("utf-8")

        return "{0},{1}".format(enc_key_str, enc_payload_str)

def main():
    if len(sys.argv) < 3:
        print("USAGE {0} public-key-file-path string-to-encrypt"
              .format(sys.argv[0]))
        return

    encryptor = Encryptor(sys.argv[1])
    data = sys.argv[2]
    print(data)
    result = encryptor.encrypt(data)
    print(result)

if __name__ == '__main__':
    main()
