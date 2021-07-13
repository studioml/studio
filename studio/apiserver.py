import time
import sys
from flask import Flask, render_template, request, redirect, abort
from studio import model
import argparse
import yaml
import json
import socket
import subprocess
import traceback
import six
import os
import requests
from requests.exceptions import ChunkedEncodingError

from .experiment import experiment_from_dict
from .auth import get_and_verify_user, get_auth
from .util import parse_verbosity
from studio.util import logs

app = Flask(__name__)


DB_PROVIDER_EXPIRATION = 1800

_db_provider_timestamp = None
_db_provider = None
_config = model.get_config()

_tensorboard_dirs = {}
_save_auth_cookie = False

logger = None


@app.route('/')
def dashboard():
    return _render('dashboard.html')


@app.route('/projects')
def projects():
    return _render('projects.html')


@app.route('/users')
def users():
    return _render('users.html')


@app.route('/all')
def all_experiments():
    return _render('all_experiments.html')


@app.route('/project/<key>')
def project_details(key):
    return _render('project_details.html', project=key)


@app.route('/user/<key>')
def user_experiments(key):
    return _render("user_details.html", user=key)


@app.route('/experiment/<key>')
def experiment(key):
    return _render("experiment_details.html", experiment=key)


@app.route('/tensorboard_exp/<key>')
def tensorboard_exp(key):
    if get_allow_tensorboard():
        experiment = _db_provider.get_experiment(key, getinfo=False)
        tb_path = _db_provider.get_artifact(experiment.artifacts['tb'])

        return tensorboard(tb_path)
    else:
        return render_template(
            'error.html',
            errormsg="Tensorboard is not allowed in hosted mode yet")


@app.route('/tensorboard_proj/<key>')
def tensorboard_proj(key):
    if get_allow_tensorboard():
        experiments = [get_db().get_experiment(e) for e in
                       get_db().get_project_experiments(key)]

        logdir = ','.join(
            [e.key + ":" + get_db().get_artifact(e.artifacts['tb'])
             for e in experiments])

        return tensorboard(logdir)
    else:
        return render_template(
            'error.html',
            errormsg="TensorBoard is not allowed in hosted mode yet")


def tensorboard(logdir):
    port = _tensorboard_dirs.get(logdir)
    if not port:

        sock = socket.socket(socket.AF_INET)
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()

        subprocess.Popen([
            'tensorboard',
            '--logdir=' + logdir,
            '--port=' + str(port)])
        time.sleep(5)  # wait for tensorboard to spin up
        _tensorboard_dirs[logdir] = port

    redirect_url = 'http://{}:{}'.format(
        six.moves.urllib.parse.urlparse(request.url).hostname,
        port)

    logger.debug('Redirecting to ' + redirect_url)
    return redirect(redirect_url)


@app.route('/api/get_experiment', methods=['POST'])
def get_experiment():
    tic = time.time()
    key = request.json['key']
    get_urls = request.json.get('get_artifact_urls', True)
    getlogger().info('Getting experiment {} '.format(key))
    try:
        experiment = get_db().get_experiment(key)
        if get_urls:
            artifacts = get_db().get_artifacts(experiment)
            for art, url in six.iteritems(artifacts):
                experiment.artifacts[art]['url'] = url

        experiment_data = experiment.__dict__
        status = 'ok'
    except BaseException:
        experiment_data = {}
        status = traceback.format_exc()

    retval = json.dumps({
        'status': status,
        'experiment': experiment_data
    })

    toc = time.time()
    getlogger().info('Processed get_experiment request in {} s'
                     .format(toc - tic))

    return retval


@app.route('/api/get_user_experiments', methods=['POST'])
def get_user_experiments():
    tic = time.time()
    myuser_id = get_and_verify_user(request, get_auth_config())
    if request.json and 'user' in request.json.keys():
        user = request.json['user']
    else:
        user = myuser_id

    # TODO check is myuser_id is authorized to do that

    getlogger().info('Getting experiments of user {}'
                     .format(user))

    experiments = [
        e for e in get_db().get_user_experiments(
            user, blocking=True)]
    status = "ok"
    retval = json.dumps({
        "status": status,
        "experiments": experiments
    })
    toc = time.time()
    getlogger().info('Processed get_user_experiments request in {} s'
                     .format(toc - tic))
    return retval


@app.route('/api/get_all_experiments', methods=['POST'])
def get_all_experiments():
    tic = time.time()
    get_and_verify_user(request, get_auth_config())

    # TODO check is myuser_id is authorized to do that

    getlogger().info('Getting all experiments')
    users = get_db().get_users()

    experiments = [e for user in users
                   for e in get_db().get_user_experiments(
                       user, blocking=False)]

    status = "ok"
    retval = json.dumps({
        "status": status,
        "experiments": experiments
    })
    toc = time.time()
    getlogger().info('Processed get_user_experiments request in {} s'
                     .format(toc - tic))
    return retval


@app.route('/api/get_projects', methods=['POST'])
def get_projects():
    tic = time.time()
    get_and_verify_user(request, get_auth_config())

    # TODO check / filter access

    projects = get_db().get_projects()
    status = "ok"

    retval = json.dumps({
        "status": status,
        "projects": projects
    })

    toc = time.time()
    getlogger().info('Processed get_projects request in {} s'
                     .format(toc - tic))
    return retval


@app.route('/api/get_users', methods=['POST'])
def get_users():
    tic = time.time()
    get_and_verify_user(request, get_auth_config())

    # TODO check / filter access

    users = get_db().get_users()
    status = "ok"

    retval = json.dumps({
        "status": status,
        "users": users
    })
    toc = time.time()
    getlogger().info('Processed get_user_experiments request in {} s'
                     .format(toc - tic))
    return retval


@app.route('/api/get_project_experiments', methods=['POST'])
def get_project_experiments():
    tic = time.time()
    get_and_verify_user(request, get_auth_config())

    project = request.json.get('project')
    if not project:
        status = "Project is none!"
        experiments = []
    else:
        # TODO check is myuser_id is authorized to do that

        getlogger().info('Getting experiments in project {}'
                         .format(project))

        experiments = get_db().get_project_experiments(project)

    status = "ok"
    retval = json.dumps({
        "status": status,
        "experiments": experiments
    })
    toc = time.time()
    getlogger().info('Processed get_project_experiments request in {} s'
                     .format(toc - tic))
    return retval


@app.route('/api/delete_experiment', methods=['POST'])
def delete_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())
    try:
        key = request.json['key']
        if get_db().can_write_experiment(key, userid):
            getlogger().info('Deleting experiment {} '.format(key))
            get_db().delete_experiment(key)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException:
        status = traceback.format_exc()

    toc = time.time()
    getlogger().info('Processed delete_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status})


@app.route('/api/stop_experiment', methods=['POST'])
def stop_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())
    try:
        key = request.json['key']
        if get_db().can_write_experiment(key, userid):
            getlogger().info('Stopping experiment {} '.format(key))
            get_db().stop_experiment(key)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException as e:
        status = e.message

    toc = time.time()
    getlogger().info('Processed stop_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status})


@app.route('/api/start_experiment', methods=['POST'])
def start_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())
    try:
        key = request.json['key']
        if get_db().can_write_experiment(key, userid):
            getlogger().info('Starting experiment {} '.format(key))
            experiment = get_db().get_experiment(key)
            get_db().start_experiment(experiment)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException as e:
        status = e.message

    toc = time.time()
    getlogger().info('Processed start_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status})


@app.route('/api/finish_experiment', methods=['POST'])
def finish_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())
    try:
        key = request.json['key']
        if get_db().can_write_experiment(key, userid):
            getlogger().info('Finishing experiment {} '.format(key))
            get_db().finish_experiment(key)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException as e:
        status = e.message

    toc = time.time()
    getlogger().info('Processed start_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status})


@app.route('/api/add_experiment', methods=['POST'])
def add_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())

    artifacts = {}
    try:
        experiment = experiment_from_dict(request.json['experiment'])
        compression = request.json.get('compression')
        compression = compression if compression else 'bzip2'

        if get_db().can_write_experiment(experiment.key, userid):
            for tag, art in six.iteritems(experiment.artifacts):
                art.pop('local', None)

            get_db().add_experiment(experiment, userid,
                                    compression=compression)
            added_experiment = get_db().get_experiment(experiment.key)

            artifacts = _process_artifacts(added_experiment)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException:
        status = traceback.format_exc()
    toc = time.time()
    getlogger().info('Processed add_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status, 'artifacts': artifacts})


@app.route('/api/checkpoint_experiment', methods=['POST'])
def checkpoint_experiment():
    tic = time.time()
    userid = get_and_verify_user(request, get_auth_config())

    artifacts = {}
    try:
        key = request.json['key']
        if get_db().can_write_experiment(key, userid):
            experiment = get_db().get_experiment(key)
            get_db().checkpoint_experiment(experiment)

            artifacts = _process_artifacts(experiment)
            status = 'ok'
        else:
            raise ValueError('Unauthorized')

    except BaseException:
        status = traceback.format_exc()

    toc = time.time()
    getlogger().info('Processed checkpoint_experiment request in {} s'
                     .format(toc - tic))

    return json.dumps({'status': status, 'artifacts': artifacts})


@app.route('/api/exchange_github_code')
def exchange_github_code():
    tic = time.time()
    code = request.args.get('code')

    getlogger().debug('Code = ' + code)

    try:
        response = requests.post(
            'https://github.com/login/oauth/access_token',
            json={
                'client_id': os.environ.get('STUDIO_GITHUB_ID'),
                'client_secret': os.environ.get('STUDIO_GITHUB_SECRET'),
                'code': code,
            })
    except ChunkedEncodingError as e:
        getlogger().info(e.__dict__)
        raise e

    if response.status_code != 200:
        abort(response.status_code)
    else:
        getlogger().info(response.content)

        toc = time.time()
        getlogger().info('Processed exchange_github_code in {} s'
                         .format(toc - tic))

        return response.content


def _process_artifacts(experiment):
    artifacts = {}
    for tag, art in six.iteritems(experiment.artifacts):
        if 'key' in art.keys():
            put_url, timestamp = get_db().store.get_artifact_url(
                art, method='PUT', get_timestamp=True)

            art['url'] = put_url
            art['timestamp'] = timestamp
            artifacts[tag] = art

    return artifacts


def get_db():
    global _config
    global _db_provider
    global _db_provider_timestamp

    if not _db_provider or \
       not _db_provider_timestamp or \
            time.time() - _db_provider_timestamp > DB_PROVIDER_EXPIRATION:
        _db_provider = model.get_db_provider(_config, blocking_auth=False)
        _db_provider_timestamp = time.time()

    return _db_provider


def get_allow_tensorboard():
    global _save_auth_cookie
    return _save_auth_cookie


def getlogger():
    global logger
    if logger is None:
        logger = logs.get_logger('studio_server')
        logger.setLevel(10)

    return logger


def get_config():
    global _config
    if _config is None:
        _config = model.get_config()
    return _config


def get_auth_config():
    return get_config()['server']['authentication']


def _render(page, **kwargs):
    tic = time.time()
    token = None
    if _save_auth_cookie:
        auth = get_auth(get_auth_config())
        if auth:
            token = auth.get_token()

    retval = render_template(
        page,
        api_key=get_db().app.api_key,
        project_id=_config['database'].get('project_id'),
        send_refresh_token="true",
        allow_tensorboard=get_allow_tensorboard(),
        github_client_id=os.environ.get('STUDIO_GITHUB_ID'),
        auth_token=token,
        **kwargs
    )
    toc = time.time()
    getlogger().info('page {} rendered in {} s'.
                     format(page, toc - tic))
    return retval


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='Studio WebUI server. \
                     Usage: studio \
                     <arguments>')

    parser.add_argument('--config', help='configuration file', default=None)
#    parser.add_argument('--guest',
#                        help='Guest mode (does not require db credentials)',
#                        action='store_true')

    parser.add_argument('--port',
                        help='port to run Flask server on',
                        type=int,
                        default=5000)

    parser.add_argument('--host',
                        help='host name.',
                        default='localhost')

    parser.add_argument(
        '--verbose', '-v',
        help='Verbosity level. Allowed vaules: ' +
             'debug, info, warn, error, crit ' +
             'or numerical value of logger levels.',
        default=None)

    args = parser.parse_args(args)
    config = model.get_config()
    if args.config:
        with open(args.config) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

    if args.verbose:
        config['verbose'] = args.verbose

#    if args.guest:
#        config['database']['guest'] = True
    global _config
    global _db_provider
    _config = config
    _db_provider = model.get_db_provider(_config)

    getlogger().setLevel(parse_verbosity(config.get('verbose', None)))

    global _save_auth_cookie
    _save_auth_cookie = True

    print('Starting Studio UI on port {0}'.format(args.port))
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
