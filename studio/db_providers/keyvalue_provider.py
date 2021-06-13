import time
from concurrent.futures import ThreadPoolExecutor, wait

from studio.util import util, logs
from studio.storage.storage_handler import StorageHandler
from studio.artifacts.artifact import Artifact
from studio.experiments.experiment import Experiment, experiment_from_dict
from studio.storage.storage_setup import get_storage_verbose_level
from studio.util.util import retry, report_fatal,\
    compression_to_extension, check_for_kb_interrupt


class KeyValueProvider:
    """Data provider for managing experiment lifecycle."""

    def __init__(
            self,
            db_config,
            handler: StorageHandler,
            compression=None):
        self.logger = logs.get_logger(self.__class__.__name__)
        self.logger.setLevel(get_storage_verbose_level())

        self.compression = compression
        if self.compression is None:
            self.compression = db_config.get('compression', None)

        self.auth = None

        self.storage_handler = handler

        self.max_keys = db_config.get('max_keys', 100)

    def _report_fatal(self, msg: str):
        report_fatal(msg, self.logger)

    def get_logger(self):
        return self.logger

    def _get_userid(self):
        userid = None
        if self.auth:
            userid = self.auth.get_user_id()
        userid = userid if userid else 'guest'
        return userid

    def _get_user_keybase(self, userid=None):
        if userid is None:
            userid = self._get_userid()

        return "users/" + userid + "/"

    def _get_experiments_keybase(self):
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def _experiment_key(self, experiment):
        if not isinstance(experiment, str):
            key = experiment.key
        else:
            key = experiment
        return key

    def add_experiment(self, experiment: Experiment,
                       userid=None, compression=None):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'

        compression = compression if compression else self.compression

        for tag, item in experiment.artifacts.items():
            art: Artifact = item
            if art.is_mutable:
                art.key = self._get_mutable_artifact_key(experiment, tag)
            else:
                if art.local_path is not None:
                    # upload immutable artifacts
                    art.key = art.upload(art.local_path)
                elif art.hash is not None:
                    art.key = self._get_immutable_artifact_key(
                        art.hash,
                        compression=compression
                    )

            if art.key is not None and art.remote_path is None:
                art.remote_path = art.storage_handler.get_qualified_location(art.key)

        userid = userid if userid else self._get_userid()
        experiment.owner = userid

        experiment_dict = experiment.to_dict()

        self._set(self._get_experiments_keybase() + experiment.key,
                  experiment_dict)

        if not experiment.from_compl_service:
            self._set(self._get_user_keybase(userid) + "experiments/" +
                  experiment.key,
                  experiment.time_added)

            if experiment.project and userid:
                self._set(self._get_projects_keybase() +
                      experiment.project + "/" +
                      experiment.key + "/owner",
                      userid)

        retry(lambda: self.checkpoint_experiment(experiment),
              sleep_time=10,
              logger=self.logger)
        self.logger.info("Added experiment %s", experiment.key)

    def _get_immutable_artifact_key(self, arthash, compression=None):
        retval = "blobstore/" + arthash + ".tar" + \
                 compression_to_extension(compression)
        return retval

    def _get_mutable_artifact_key(self, experiment: Experiment, tag: str) -> str:
        return self._get_experiments_keybase() + \
            experiment.key + '/' + tag + '.tar'

    def start_experiment(self, experiment):
        time_started = time.time()
        experiment.time_started = time_started
        experiment.status = 'running'

        experiment_dict = self._get(self._get_experiments_keybase() +
                                    experiment.key)
        experiment_dict['time_started'] = time_started
        experiment_dict['status'] = 'running'

        self._set(self._get_experiments_keybase() +
                  experiment.key,
                  experiment_dict)

        self.checkpoint_experiment(experiment)

    def stop_experiment(self, key):
        # can be called remotely (the assumption is
        # that remote worker checks experiments status periodically,
        # and if it is 'stopped', kills the experiment)
        key = self._experiment_key(key)

        experiment_data = self._get(self._get_experiments_keybase() +
                                    key)

        experiment_data['status'] = 'stopped'

        self._set(self._get_experiments_keybase() +
                  key, experiment_data)

    def finish_experiment(self, experiment):
        time_finished = time.time()
        key = self._experiment_key(experiment)
        if not isinstance(experiment, str):
            experiment.status = 'finished'
            experiment.time_finished = time_finished

        experiment_dict = self._get(
            self._get_experiments_keybase() + key)

        experiment_dict['status'] = 'finished'
        experiment_dict['time_finished'] = time_finished

        self._set(self._get_experiments_keybase() +
                  key, experiment_dict)

    def delete_experiment(self, experiment):
        if experiment is None:
            return
        if isinstance(experiment, str):
            try:
                experiment = self.get_experiment(experiment, getinfo=False)
                experiment_key = experiment.key
            except BaseException:
                check_for_kb_interrupt()
                return
        else:
            experiment_key = experiment.key

        experiment_dict = self._get(self._get_experiments_keybase() +
                                    experiment_key)
        if experiment_dict is None:
            self.logger.error("FAILED to delete experiment %s: NOT FOUND.",
                              experiment_key)
            return

        from_compl_service: bool = experiment_dict.get('from_compl_service', False)
        experiment_owner = experiment_dict.get('owner')
        if experiment_owner is not None and not from_compl_service:
            self._delete(self._get_user_keybase(experiment_owner) +
                     'experiments/' + experiment_key, shallow=False)

        if experiment is not None:
            for tag, art in experiment.artifacts.items():
                if art.key is not None and art.is_mutable:
                    msg: str =\
                        ('Deleting artifact {0} from the store, ' +
                         'artifact key {1}').format(tag, art.key)
                    self.logger.debug(msg)
                    art.delete()

            if experiment.project is not None and not from_compl_service:
                self._delete(
                    self._get_projects_keybase() +
                    experiment.project + "/" + experiment_key + "/" + "owner",
                    shallow=False)

        self._delete(self._get_experiments_keybase() + experiment_key, shallow=False)


    def cleanup(self):
        if self.storage_handler is not None:
            self.storage_handler.cleanup()


    def checkpoint_experiment(self, experiment):
        key = self._experiment_key(experiment)
        key_path = self._get_experiments_keybase() + key

        self.logger.debug('checkpointing %s', key_path)

        experiment_dict = self._get(key_path)

        workers = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            for _, art in experiment.artifacts.items():
                if art.is_mutable and art.local_path is not None:
                    workers.append(executor.submit(art.upload, None))
            wait(workers)

        for worker in workers:
            try:
                worker.result()
            except Exception as exc:
                # If any of artifact savers failed and threw an exception,
                # rethrow it to signal overall checkpoint failure
                raise exc

        checkpoint_time = time.time()
        experiment.time_last_checkpoint = checkpoint_time
        experiment_dict['time_last_checkpoint'] = checkpoint_time

        self._set(key_path, experiment_dict)

    def _get_experiment_info(self, experiment: Experiment):
        info = {}
        type_found = False

        if not type_found:
            info['type'] = 'unknown'

        info['logtail'] = self._get_experiment_logtail(experiment)
        return info

    def _get_experiment_logtail(self, experiment: Experiment):
        try:
            tarf = experiment.artifacts['output'].stream()
            if not tarf:
                return None
            tarf_member = tarf.members[0]
            while tarf_member is not None and tarf_member.name == '':
                tarf_member = tarf.next()

            logdata = tarf.extractfile(tarf_member).read()
            logdata = util.remove_backspaces(logdata).split('\n')
            return logdata
        except BaseException as exc:
            self.logger.debug('Getting experiment logtail raised an exception: %s',
                              repr(exc))
            check_for_kb_interrupt()
            return None

    def get_experiment(self, key, getinfo=True) -> Experiment:
        data = self._get(self._get_experiments_keybase() + key)
        if data is None:
            return None

        data['key'] = key

        experiment_stub = experiment_from_dict(data)

        expinfo = {}
        if getinfo:
            try:
                expinfo = self._get_experiment_info(experiment_stub)
            except Exception as exc:
                self.logger.info(
                    "Exception %s while info download for %s", repr(exc), key)

        return experiment_from_dict(data, expinfo)

    def get_user_experiments(self, userid=None):
        if userid and '@' in userid:
            users = self.get_users()
            user_ids = [u for u in users if users[u].get('email') == userid]
            if len(user_ids) < 1:
                return None
            userid = user_ids[0]

        experiment_keys = self._get(
            self._get_user_keybase(userid) + "experiments/", shallow=True)
        if not experiment_keys:
            experiment_keys = []

        return experiment_keys

    def get_project_experiments(self, project):
        experiment_keys = self._get(self._get_projects_keybase() +
                                    project)
        if not experiment_keys:
            experiment_keys = {}

        return experiment_keys.keys()

    def get_artifacts(self, key):
        if isinstance(key, str):
            experiment = self.get_experiment(key, getinfo=False)
        else:
            experiment = key

        retval = {}
        for tag, art in experiment.artifacts.items():
            url = art.get_url()
            if url is not None:
                retval[tag] = url

        return retval

    def get_artifact(self, artifact, local_path=None, only_newer=True):
        return artifact.download(
            local_path=local_path,
            only_newer=only_newer)

    def get_projects(self):
        return self._get(self._get_projects_keybase(), shallow=True)

    def get_users(self):
        user_ids = self._get('users/', shallow=True)
        retval = {}
        if user_ids:
            for user_id in user_ids:
                retval[user_id] = {
                    'email': self._get('users/' + user_id + '/email')
                }
        return retval

    def refresh_auth_token(self, email, refresh_token):
        if self.auth:
            self.auth.refresh_token(email, refresh_token)

    def is_auth_expired(self):
        if self.auth:
            return self.auth.expired
        return False

    def can_write_experiment(self, key=None, user=None):
        assert key is not None
        user = user if user else self._get_userid()

        experiment = self._get(
            self._get_experiments_keybase() + key)

        if experiment:
            owner = experiment.get('owner')
            if owner is None or owner == 'guest':
                return True
            return owner == user
        return True

    def register_user(self, userid, email):
        keypath = self._get_user_keybase(userid) + 'email'
        existing_email = self._get(keypath)
        if existing_email != email:
            self._set(keypath, email)

    def get_storage_handler(self):
        return self.storage_handler

    def _get(self, key, shallow=False):
        raise NotImplementedError("Not implemented: _get")

    def _set(self, key, value):
        raise NotImplementedError("Not implemented: _set")

    def _delete(self, key, shallow=True):
        raise NotImplementedError("Not implemented: _delete")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
