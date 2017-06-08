import time
from flask import Flask, render_template, request, redirect
import model
import argparse
import yaml
import logging
import json
from functools import wraps

logging.basicConfig()

app = Flask(__name__)


_db_provider = None
logger = None

def authenticated(redirect_after):
    def auth_decorator(func):
        @wraps(func)
        def auth_wrapper(**kwargs):
            if _db_provider.auth.expired:
                formatted_redirect = redirect_after
                for k,v in kwargs.iteritems():
                    formatted_redirect = formatted_redirect.replace('<' + k + '>', v)
                logger.debug(get_auth_url() + formatted_redirect)
                return redirect(get_auth_url() + formatted_redirect)

            return func(**kwargs)

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
    experiments = _db_provider.get_user_experiments()
    return render_template(
        "dashboard.html",
        experiments=sorted(experiments, key=lambda e: -e.time_added))

@app.route('/experiments/<key>')
@authenticated('/experiments/<key>')
def experiment(key):
    experiment = _db_provider.get_experiment(key)
    return render_template("experiment_details.html", experiment=experiment)


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
    projects = _db_provider.get_projects()
    return render_template(
        "project_details.html",
        project_name=key,
        project_dict=projects[key])


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
        experiments=sorted(experiments, key=lambda e: -e.time_added))


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

    args = parser.parse_args()
    config = model.get_default_config()
    if args.config:
        with open(args.config) as f:
            config.update(yaml.load(f))

#    if args.guest:
#        config['database']['guest'] = True

    global _db_provider
    _db_provider = model.get_db_provider(config, blocking_auth=False)

    global logger
    logger = logging.getLogger('studio')
    logger.setLevel(10)

    app.run(port=args.port, debug=True)


if __name__ == "__main__":
    main()
