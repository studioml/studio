import openssh_key.private_key_list as pkl
from openssh_key.key import PublicKey

class Ed25519KeyUtil:

    @classmethod
    def parse_private_key_file(cls, filepath: str, logger):
        """
        Parse a file with ed25519 private key in OPEN SSH PRIVATE key format.
        :param filepath: file path to a key file
        :param logger: logger to use for messages
        :return: (public key part as bytes, private key part as bytes)
        """
        contents: str = ''
        try:
            with open(filepath, "r") as f:
                contents = f.read()
        except Exception as exc:
            if logger is not None:
                logger.error("FAILED to read keyfile %s: %s",
                             filepath, exc)
            return None, None
        try:
            key_data = pkl.PrivateKeyList.from_string(contents)
            data_public = key_data[0].private.params['public']
            data_private = key_data[0].private.params['private_public']
            return data_public, data_private[:32]
        except Exception as exc:
            if logger is not None:
                logger.error("FAILED to decode keyfile format %s: %s",
                         filepath, exc)
            return None, None

    @classmethod
    def parse_public_key_file(cls, filepath: str, logger):
        """
        Parse a file with ed25519 public.
        :param filepath: file path to a key file
        :param logger: logger to use for messages
        :return: public key part as bytes
        """
        contents: str = ''
        try:
            with open(filepath, "r") as f:
                contents = f.read()
        except Exception as exc:
            if logger is not None:
                logger.error("FAILED to read keyfile %s: %s",
                             filepath, exc)
            return None, None
        try:
            key_data = PublicKey.from_string(contents)
            data_public = key_data.params['public']
            return data_public
        except Exception as exc:
            if logger is not None:
                logger.error("FAILED to decode keyfile format %s: %s",
                         filepath, exc)
            return None
