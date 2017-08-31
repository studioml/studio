import logging
import requests

from tartifact_store import TartifactStore
logging.basicConfig()


class HTTPArtifactStore(TartifactStore):
    def __init__(self, post, verbose=10):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        self.post = post

        super(HTTPArtifactStore, self).__init__(False)

    def _upload_file(self, key, local_path):
        with open(local_path, 'rb') as f:
            resp = requests.post(
                self.post['url'],
                files={'file': f},
                data=self.post['fields'])

        if resp.status_code != 204:
            # You'd think the code that we are checking
            # against should be 200 (OK)
            # but for some reason S3 runs the operation
            # correctly, and yet returns 204
            self.logger.error(str(resp))

    def _download_file(self, key, local_path):
        raise NotImplementedError

    def _delete_file(self, key):
        raise NotImplementedError

    def _get_file_url(self, key):
        raise NotImplementedError

    def _get_file_post(self, key):
        return self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key)

    def _get_file_timestamp(self, key):
        raise NotImplementedError

    def get_qualified_location(self, key):
        return self.endpoint + '/' + key
