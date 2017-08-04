import time
from flask import Flask, render_template, request, redirect
import model
import argparse
import yaml
import logging
import json
from functools import wraps
import socket
import subprocess
from urlparse import urlparse
from requests.exceptions import HTTPError
from multiprocessing.pool import ThreadPool

import fs_tracker

logging.basicConfig()

app = Flask(__name__)


_db_provider = None
_tensorboard_dirs = {}
logger = None


def authenticated(redirect_after):
    def auth_decorator(func):
        @wraps(func)
        def auth_wrapper(**kwargs):
            if _db_provider.auth and _db_provider.auth.expired:
                formatted_redirect = redirect_after
                for k, v in kwargs.iteritems():
                    formatted_redirect = formatted_redirect.replace(
                        '<' + k + '>', v)
                logger.debug(get_auth_url() + formatted_redirect)
                return redirect(get_auth_url() + formatted_redirect)

            try:
                return func(**kwargs)
            except HTTPError as e:
                return render_template('error.html', errormsg=str(e))

        return auth_wrapper
    return auth_decorator


@app.template_filter('format_time')
def format_time(timestamp):
    return time.strftime(
        '%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@app.route('/auth_response', methods=['POST'])
def auth_response():
    auth_dict = json.loads(request.form['data'])
    logger.debug(auth_dict.keys())
    expires = auth_dict['stsTokenManager']['expirationTime'] / 1000
    logger.debug("Authentication successful. Token duration (s): {}"
                 .format(expires - time.time()))
    logger.debug("auth_dict = " + str(auth_dict))

    refresh_token = auth_dict['stsTokenManager']['refreshToken']
    email = auth_dict['email']

    logger.debug('refresh_token = ' + refresh_token)
    logger.debug('email = ' + email)

    _db_provider.refresh_auth_token(email, refresh_token)
    logger.debug("Authentication successfull, response" + str(request.form))
    return redirect(request.form['redirect'])


@app.route('/')
@authenticated('/')
def dashboard():
    tic = time.time()
    global logger

    experiments = _db_provider.get_user_experiments(blocking=False)
    toc = time.time()
    logger.debug('Dashboard (/) prepared in {} s'.format(toc - tic))
    return render_template("dashboard.html", experiments=experiments)


@app.route('/all')
@authenticated('/all')
def all_experiments():
    tic = time.time()
    global logger

    experiments = []
    users = _db_provider.get_users()
    for user in users:
        experiments += _db_provider.get_user_experiments(user, blocking=False)

    toc = time.time()
    logger.debug(
        'All experiments page (/all) prepared in {} s'.format(toc - tic))
    return render_template("all_experiments.html", experiments=experiments)


@app.route('/experiments/<key>')
@authenticated('/experiments/<key>')
def experiment(key):
    experiment = _db_provider.get_experiment(key, getinfo=True)
    artifacts_urls = _db_provider.get_artifacts(key)
    logtail = experiment.info.get('logtail')
    info = experiment.info
    return render_template("experiment_details.html",
                           experiment=experiment,
                           artifacts=artifacts_urls,
                           logtail=logtail,
                           info=info)


@app.route('/tensorboard_exp/<key>')
@authenticated('/tensorboard_exp/<key>')
def tensorboard_exp(key):
    experiment = _db_provider.get_experiment(key, getinfo=False)
    tb_path = _db_provider.store.get_artifact(experiment.artifacts['tb'])

    return tensorboard(tb_path)


@app.route('/tensorboard_proj/<key>')
@authenticated('/tensorboard_proj/<key>')
def tensorboard_proj(key):
    experiments = _db_provider.get_project_experiments(key)
    logdir = ','.join(
        [e.key + ":" + fs_tracker.get_tensorboard_dir(e.key)
         for e in experiments])

    return tensorboard(logdir)


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


@app.route('/projects')
@authenticated('/projects')
def projects():
    projects = _db_provider.get_projects()
    if not projects:
        projects = {}
    return render_template("projects.html", projects=projects)


@app.route('/project/<key>')
@authenticated('/project/<key>')
def project_details(key):
    experiments = _db_provider.get_project_experiments(key)
    return render_template(
        "project_details.html",
        project_name=key,
        experiments=experiments,
        key_list=json.dumps([e.key for e in experiments]))


@app.route('/users')
@authenticated('/users')
def users():
    users = _db_provider.get_users()
    return render_template("users.html", users=users)


@app.route('/user/<key>')
@authenticated('/user/<key>')
def user_experiments(key):
    experiments = _db_provider.get_user_experiments(key)
    users = _db_provider.get_users()
    email = users[key]['email'] if 'email' in users[key].keys() else None
    return render_template(
        "user_details.html",
        user=key,
        email=email,
        experiments=experiments)


@app.route('/delete_experiment/<key>')
@authenticated('/delete_experiment/<key>')
def delete_experiment(key):
    _db_provider.delete_experiment(key)
    return redirect('/')


@app.route('/stop_experiment/<key>')
@authenticated('/stop_experiment/<key>')
def stop_experiment(key):
    _db_provider.stop_experiment(key)
    return redirect('/experiments/' + key)


@app.route('/delete_all/')
@authenticated('/delete_all/')
def delete_all_experiments():
    pool = ThreadPool(128)
    experiments = _db_provider.get_user_experiments()
    pool.map(_db_provider.delete_experiment, experiments)

    return redirect('/')


def get_auth_url():
    return ("https://{}/index.html?" +
            "authurl=http://{}/auth_response&redirect=").format(
        _db_provider.get_auth_domain(),
        request.host)


def main():
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio WebUI server. \
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

    print('Starting TensorFlow Studio on port {0}'.format(args.port))
    app.run(host='0.0.0.0', port=args.port, debug=True)


if __name__ == "__main__":
    main()
