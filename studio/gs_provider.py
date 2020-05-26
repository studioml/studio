import json
import time
import re
from .keyvalue_provider import KeyValueProvider
from .gcloud_artifact_store import GCloudArtifactStore
from .util import timeit


class GSProvider(KeyValueProvider):

    def __init__(self, config, blocking_auth=True, verbose=10, store=None):
        self.config = config
        self.bucket = config.get('bucket', 'studioml-meta')

        self.meta_store = GCloudArtifactStore(config, verbose)
        super(GSProvider, self).__init__(
            config,
            blocking_auth,
            verbose,
            store)

    def _get(self, key, shallow=False):
        bucket = self.meta_store._get_bucket_obj()
        retval = {}
        if shallow:
            blob_iterator = bucket.list_blobs(
                prefix=key, delimiter='/')
            bloblist = list(blob_iterator)
            blobnames = {b.name for b in bloblist}

            prefixes = blob_iterator.prefixes
            suffixes = [re.sub('^' + key, '', p) for p in prefixes | blobnames]

            retval = set({})
            for s in suffixes:
                if s.endswith('/'):
                    retval.add(s[:-1])
                else:
                    retval.add(s)

            return retval

        else:
            blob_iterator = bucket.list_blobs(prefix=key)
            for blob in blob_iterator:
                suffix = re.sub('^' + key, '', blob.name)
                if suffix == '':
                    return json.loads(blob.download_as_string())

                path = suffix.split('/')
                path = [p for p in path if p != '']
                current_dict = retval
                for subdir in path[:-1]:
                    if subdir != '':
                        if subdir not in current_dict.keys():
                            current_dict[subdir] = {}
                        current_dict = current_dict[subdir]

                try:
                    current_dict[path[-1]] = json.loads(
                        blob.download_as_string())
                except BaseException:
                    pass

        if not any(retval):
            return None
        else:
            return retval

    def _delete(self, key):
        self.meta_store._delete_file(key)

    def _set(self, key, value):
        no_retries = 10
        sleep_time = 1
        for i in range(no_retries):
            try:
                self.meta_store._get_bucket_obj().blob(key) \
                    .upload_from_string(json.dumps(value))
                break
            except BaseException as e:
                self.logger.error('uploading data raised an exception:')
                self.logger.exception(e)

            time.sleep(sleep_time)
