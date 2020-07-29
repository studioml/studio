import time
import os
import six
import re
from threading import Thread

from . import util, git_util, logs
from .firebase_artifact_store import FirebaseArtifactStore
from .auth import get_auth
from .experiment import experiment_from_dict
from .tartifact_store import get_immutable_artifact_key
from .util import timeit, retry


class KeyValueProvider(object):
    """Data provider for Firebase."""

    def __init__(
            self,
            db_config,
            blocking_auth=True,
            verbose=10,
            store=None,
            compression=None):
        guest = db_config.get('guest')

        self.logger = logs.getLogger(self.__class__.__name__)
        self.logger.setLevel(verbose)

        self.compression = compression
        if self.compression is None:
            self.compression = db_config.get('compression')

        self.auth = None
        if not guest and 'serviceAccount' not in db_config.keys():
            self.auth = get_auth(
                db_config['authentication'],
                blocking_auth
            )

        self.store = store if store else FirebaseArtifactStore(
            db_config,
            verbose=verbose,
            blocking_auth=blocking_auth,
            compression=self.compression
        )

        if self.auth and not self.auth.is_expired():
            self.register_user(None, self.auth.get_user_email())

        self.max_keys = db_config.get('max_keys', 100)

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

    def _get_experiments_keybase(self, userid=None):
        return "experiments/"

    def _get_projects_keybase(self):
        return "projects/"

    def add_experiment(self, experiment, userid=None, compression=None):
        self._delete(self._get_experiments_keybase() + experiment.key)
        experiment.time_added = time.time()
        experiment.status = 'waiting'

        compression = compression if compression else self.compression

        if 'local' in experiment.artifacts['workspace'].keys() and \
                os.path.exists(experiment.artifacts['workspace']['local']):
            self.logger.info("git location for experiment " +
                             experiment.artifacts['workspace']['local'])
            experiment.git = git_util.get_git_info(
                experiment.artifacts['workspace']['local'])

        for tag, art in six.iteritems(experiment.artifacts):
            if art['mutable']:
                art['key'] = self._get_experiments_keybase() + \
                    experiment.key + '/' + tag + '.tar' + \
                    util.compression_to_extension(compression)
            else:
                if 'local' in art.keys():
                    # upload immutable artifacts
                    art['key'] = self.store.put_artifact(art)
                elif 'hash' in art.keys():
                    art['key'] = get_immutable_artifact_key(
                        art['hash'],
                        compression=compression
                    )

            key = art.get('key')
            if key is not None:
                art['qualified'] = self.store.get_qualified_location(key)
                art['bucket'] = self.store.get_bucket()
            elif art.get('qualified'):
                qualified = art.get('qualified')
                bucket = re.search('(?<=://)[^/]+(?=/)', qualified).group(0)
                if bucket.endswith('.com'):
                    bucket = re.search(
                        '(?<=' + re.escape(bucket) + '/)[^/]+(?=/)',
                        qualified
                    ).group(0)

                key = re.search('(?<=' + bucket + '/).+\Z', qualified).group(0)
                # art['bucket'] = bucket
                # art['key'] = key

        userid = userid if userid else self._get_userid()
        experiment.owner = userid

        experiment_dict = experiment.__dict__.copy()

        self._set(self._get_experiments_keybase() + experiment.key,
                  experiment_dict)

        self._set(self._get_user_keybase(userid) + "experiments/" +
                  experiment.key,
                  experiment.time_added)

        if experiment.project and userid:
            self._set(self._get_projects_keybase() +
                      experiment.project + "/" +
                      experiment.key + "/owner",
                      userid)

        retry(lambda: self.checkpoint_experiment(experiment, blocking=True),
              sleep_time=10,
              logger=self.logger)
        self.logger.info("Added experiment " + experiment.key)

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
        if not isinstance(key, six.string_types):
            key = key.key

        experiment_data = self._get(self._get_experiments_keybase() +
                                    key)

        experiment_data['status'] = 'stopped'

        self._set(self._get_experiments_keybase() +
                  key, experiment_data)

    def finish_experiment(self, experiment):
        time_finished = time.time()
        if not isinstance(experiment, six.string_types):
            key = experiment.key
            experiment.status = 'finished'
            experiment.time_finished = time_finished
        else:
            key = experiment

        experiment_dict = self._get(
            self._get_experiments_keybase() + key)

        experiment_dict['status'] = 'finished'
        experiment_dict['time_finished'] = time_finished

        self._set(self._get_experiments_keybase() +
                  key, experiment_dict)

    def delete_experiment(self, experiment):
        if isinstance(experiment, six.string_types):
            experiment_key = experiment
            try:
                experiment = self.get_experiment(experiment)
                experiment_key = experiment.key
            except BaseException:
                experiment = None
        else:
            experiment_key = experiment.key

        experiment_owner = self._get(self._get_experiments_keybase() +
                                     experiment_key).get('owner')

        self._delete(self._get_user_keybase(experiment_owner) +
                     'experiments/' + experiment_key)
        if experiment is not None:
            for tag, art in six.iteritems(experiment.artifacts):
                if art.get('key') is not None and art['mutable']:
                    self.logger.debug(
                        ('Deleting artifact {} from the store, ' +
                         'artifact key {}').format(tag, art['key']))
                    self.store.delete_artifact(art)

            if experiment.project is not None:
                self._delete(
                    self._get_projects_keybase() +
                    experiment.project +
                    "/" +
                    experiment_key)

        self._delete(self._get_experiments_keybase() + experiment_key)

    def checkpoint_experiment(self, experiment, blocking=False):
        if not isinstance(experiment, six.string_types):
            key = experiment.key
        else:
            key = experiment

        self.logger.debug(('checkpointing {}'.format(
            self._get_experiments_keybase() + key)))

        experiment_dict = self._get(self._get_experiments_keybase() + key)

        checkpoint_threads = [
            Thread(
                target=self.store.put_artifact,
                args=(art,))
            for _, art in six.iteritems(experiment.artifacts)
            if art['mutable'] and art.get('local')]

        for t in checkpoint_threads:
            t.start()

        checkpoint_time = time.time()
        experiment.time_last_checkpoint = checkpoint_time
        experiment_dict['time_last_checkpoint'] = checkpoint_time

        self._set(self._get_experiments_keybase() +
                  key, experiment_dict)

        if blocking:
            for t in checkpoint_threads:
                t.join()
        else:
            return checkpoint_threads

    def _get_experiment_info(self, experiment):
        info = {}
        type_found = False

        if not type_found:
            info['type'] = 'unknown'

        info['logtail'] = self._get_experiment_logtail(experiment)

        if experiment.metric is not None:
            metric_str = experiment.metric.split(':')
            metric_name = metric_str[0]
            metric_type = metric_str[1] if len(metric_str) > 1 else None

            tbtar = self.store.stream_artifact(experiment.artifacts['tb'])

            if metric_type == 'min':
                def metric_accum(x, y): return min(x, y) if x else y
            elif metric_type == 'max':
                def metric_accum(x, y): return max(x, y) if x else y
            else:
                def metric_accum(x, y): return y

            metric_value = None
            for f in tbtar:
                if f.isreg():
                    for e in util.event_reader(tbtar.extractfile(f)):
                        for v in e.summary.value:
                            if v.tag == metric_name:
                                metric_value = metric_accum(
                                    metric_value, v.simple_value)

            info['metric_value'] = metric_value

        return info

    def _get_experiment_logtail(self, experiment):
        try:
            tarf = self.store.stream_artifact(experiment.artifacts['output'])
            if not tarf:
                return None
            tarf_member = tarf.members[0]
            while tarf_member is not None and tarf_member.name == '':
                tarf_member = tarf.next()

            logdata = tarf.extractfile(tarf_member).read()
            logdata = util.remove_backspaces(logdata).split('\n')
            return logdata
        except BaseException as e:
            self.logger.debug('Getting experiment logtail raised an exception: {0}'
                              .format(repr(e)))
            return None

    def get_experiment(self, key, getinfo=True):
        data = self._get(self._get_experiments_keybase() + key)
        if data is None:
            return None

        data['key'] = key

        experiment_stub = experiment_from_dict(data)

        expinfo = {}
        if getinfo:
            try:
                expinfo = self._get_experiment_info(experiment_stub)

            except Exception as e:
                self.logger.info(
                    "Exception {0} while info download for {1}".format(
                        e, key))

        return experiment_from_dict(data, expinfo)

    def get_user_experiments(self, userid=None, blocking=True):
        if userid and '@' in userid:
            users = self.get_users()
            user_ids = [u for u in users if users[u].get('email') == userid]
            if len(user_ids) < 1:
                return None
            else:
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
        if isinstance(key, six.string_types):
            experiment = self.get_experiment(key, getinfo=False)
        else:
            experiment = key

        retval = {}
        if experiment.artifacts is not None:
            for tag, art in six.iteritems(experiment.artifacts):
                url = self.store.get_artifact_url(art)
                if url is not None:
                    retval[tag] = url

        return retval

    def get_artifact(self, artifact, local_path=None, only_newer=True):
        return self.store.get_artifact(artifact,
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
        else:
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
            else:
                return (owner == user)
        else:
            return True

    def register_user(self, userid, email):
        keypath = self._get_user_keybase(userid) + 'email'
        existing_email = self._get(keypath)
        if existing_email != email:
            self._set(keypath, email)

    def get_artifact_store(self):
        return self.store

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.store:
            self.store.__exit__()
