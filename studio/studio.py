import time
from flask import Flask, render_template, request, redirect
import model
import argparse
import yaml
import logging
import json
import socket
import subprocess
from urlparse import urlparse

import google.oauth2.id_token
import google.auth.transport.requests

logging.basicConfig()

app = Flask(__name__)


_db_provider = None
_tensorboard_dirs = {}
_grequest = google.auth.transport.requests.Request()
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
        tb_path = _db_provider.store.get_artifact(experiment.artifacts['tb'])

        return tensorboard(tb_path)
    else:
        return render_template(
            'error.html',
            errormsg="Tensorboard is not allowed in hosted mode yet")


@app.route('/tensorboard_proj/<key>')
def tensorboard_proj(key):
    if get_allow_tensorboard():
        experiments = get_db().get_project_experiments(key)

        logdir = ','.join(
            [e.key + ":" + get_db().store.get_artifact(e.artifacts['tb'])
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
        urlparse(request.url).hostname,
        port)

    logger.debug('Redirecting to ' + redirect_url)
    return redirect(redirect_url)


@app.route('/api/get_experiment', methods=['POST'])
def get_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Getting experiment {} '.format(key))
    try:
        experiment = get_db().get_experiment(key).__dict__
        artifacts = get_db().get_artifacts(key)
        for art, url in artifacts.iteritems():
            experiment['artifacts'][art]['url'] = url

        status = 'ok'
    except BaseException as e:
        experiment = {}
        status = e.message

    retval = json.dumps({'status': status, 'experiment': experiment})

    toc = time.time()
    logger.info('Processed get_experiment request in {} s'
                .format(toc - tic))

    return retval


@app.route('/api/get_user_experiments', methods=['POST'])
def get_user_experiments():
    tic = time.time()

    myuser_id = get_and_verify_user(request)
    if request.json and 'user' in request.json.keys():
        user = request.json['user']
    else:
        user = myuser_id

    # TODO check is myuser_id is authorized to do that

    logger.info('Getting experiments of user {}'
                .format(user))

    experiments = get_db().get_user_experiments(user, blocking=True)
    status = "ok"
    retval = json.dumps({
        "status": status,
        "experiments": [e.__dict__ for e in experiments]
    })
    toc = time.time()
    logger.info('Processed get_user_experiments request in {} s'
                .format(toc - tic))
    return retval


@app.route('/api/get_projects', methods=['POST'])
def get_projects():
    tic = time.time()
    myuser_id = get_and_verify_user(request)

    # TODO check / filter access

    projects = get_db().get_projects()
    status = "ok"

    retval = json.dumps({
        "status": status,
        "projects": projects
    })

    toc = time.time()
    logger.info('Processed get_projects request in {} s'
                .format(toc - tic))
    return retval


@app.route('/api/get_users', methods=['POST'])
def get_users():
    tic = time.time()
    myuser_id = get_and_verify_user(request)

    # TODO check / filter access

    users = get_db().get_users()
    status = "ok"

    retval = json.dumps({
        "status": status,
        "users": users
    })
    toc = time.time()
    logger.info('Processed get_user_experiments request in {} s'
                .format(toc - tic))
    return retval


@app.route('/api/get_project_experiments', methods=['POST'])
def get_project_experiments():
    tic = time.time()
    myuser_id = get_and_verify_user(request)

    project = request.json.get('project')
    if not project:
        status = "Project is none!"
        experiments = []
    else:
        # TODO check is myuser_id is authorized to do that

        logger.info('Getting experiments in project {}'
                    .format(project))

        experiments = get_db().get_project_experiments(project)

    status = "ok"
    retval = json.dumps({
        "status": status,
        "experiments": [e.__dict__ for e in experiments]
    })
    toc = time.time()
    logger.info('Processed get_project_experiments request in {} s'
                .format(toc - tic))
    return retval


@app.route('/api/delete_experiment', methods=['POST'])
def delete_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Deleting experiment {} '.format(key))
    try:
        get_db().delete_experiment(key)
        status = 'ok'
    except BaseException as e:
        status = e.message

    toc = time.time()
    logger.info('Processed delete_experiment request in {} s'
                .format(toc - tic))

    return json.dumps({'status': status})


@app.route('/api/stop_experiment', methods=['POST'])
def stop_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Deleting experiment {} '.format(key))
    try:
        get_db().stop_experiment(key)
        status = 'ok'
    except BaseException as e:
        status = e.message

    toc = time.time()
    logger.info('Processed stop_experiment request in {} s'
                .format(toc - tic))

    return json.dumps({'status': status})


def get_and_verify_user(request):
    if not request.headers or 'Authorization' not in request.headers.keys():
        return None

    auth_token = request.headers['Authorization'].split(' ')[-1]
    claims = google.oauth2.id_token.verify_firebase_token(
        auth_token, _grequest)
    if not claims:
        return None
    else:
        global _save_auth_cookie
        if _save_auth_cookie and request.json and \
                'refreshToken' in request.json.keys():
            get_db().refresh_auth_token(
                claims['email'],
                request.json['refreshToken']
            )

        return claims['user_id']


def get_db():
    global _db_provider
    if not _db_provider:
        _db_provider = model.get_db_provider()

    return _db_provider


def get_allow_tensorboard():
    global _save_auth_cookie
    return _save_auth_cookie


def getlogger():
    global logger
    return logger


def _render(page, **kwargs):
    tic = time.time()
    retval = render_template(
        page,
        api_key=get_db().app.api_key,
        project_id='studio-ed756',
        send_refresh_token="true",
        allow_tensorboard=get_allow_tensorboard(),
        **kwargs
    )
    toc = time.time()
    getlogger().info('page {} rendered in {} s'.
                     format(page, toc - tic))
    return retval


def main():
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

    parser.add_argument(
        '--verbose', '-v',
        help='Verbosity level. Allowed vaules: ' +
             'debug, info, warn, error, crit ' +
             'or numerical value of logger levels.',
        default=None)

    args = parser.parse_args()
    config = model.get_config()
    if args.config:
        with open(args.config) as f:
            config.update(yaml.load(f))

    if args.verbose:
        config['verbose'] = args.verbose

#    if args.guest:
#        config['database']['guest'] = True

    global _db_provider
    _db_provider = model.get_db_provider(config, blocking_auth=False)

    global logger
    logger = logging.getLogger('studio')
    logger.setLevel(model.parse_verbosity(config.get('verbose')))

    global _save_auth_cookie
    _save_auth_cookie = True

    print('Starting Studio UI on port {0}'.format(args.port))
    app.run(host='0.0.0.0', port=args.port, debug=True)


if __name__ == "__main__":
    main()
