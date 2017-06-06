import time
from flask import Flask, render_template, request, redirect
import model
import argparse
import yaml
import logging
import json
import time
 
logging.basicConfig()

app = Flask(__name__)


_db_provider = None

logger = logging.getLogger('studio')
logger.setLevel(10)

auth_url = 'http://localhost:5004/index.html'

@app.template_filter('format_time')
def format_time(timestamp):
    return time.strftime(
        '%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@app.route('/auth_response', methods=['POST'])
def auth_response():
    #logger.info(str(request.form['data']))
    auth_dict = json.loads(request.form['data'])
    logger.debug(auth_dict.keys())
    expires = auth_dict['stsTokenManager']['expirationTime'] / 1000
    logger.debug("Authentication successful. Token duration (s): {}".format(expires - time.time())) 
    logger.debug("auth_dict = " + str(auth_dict))
  
    refresh_token = auth_dict['stsTokenManager']['refreshToken']
    email = auth_dict['email']

    logger.debug('refresh_token = ' + refresh_token)
    logger.debug('email = ' + email)

    _db_provider.auth.refresh_token(email, refresh_token)
    #return redirect("/")
    
    return "Authentication successfull with token" + str(request.form['data'])

@app.route('/')
def dashboard():
    if _db_provider.auth.expired:
        return redirect(auth_url)

    experiments = _db_provider.get_user_experiments()
    return render_template("dashboard.html", 
            experiments=sorted(experiments, key=lambda e:-e.time_added))


@app.route('/experiments/<key>')
def experiment(key):
    experiment = _db_provider.get_experiment(key)
    return render_template("experiment_details.html", experiment=experiment)


@app.route('/projects')
def projects():
    projects = _db_provider.get_projects()
    if not projects:
        projects = {}
    return render_template("projects.html", projects=projects)


@app.route('/project/<key>')
def project_details(key):
    projects = _db_provider.get_projects()
    return render_template(
        "project_details.html",
        project_name=key,
        project_dict=projects[key])


@app.route('/users')
def users():
    if _db_provider.auth.expired:
        return redirect(auth_url)

    users = _db_provider.get_users()
    return render_template("users.html", users=users)


@app.route('/user/<key>')
def user_experiments(key):
    experiments = _db_provider.get_user_experiments(key)
    users = _db_provider.get_users()
    email = users[key]['email'] if 'email' in users[key].keys() else None
    return render_template(
        "user_details.html",
        user=key,
        email=email,
        experiments=sorted(experiments, key=lambda e:-e.time_added))


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
    _db_provider = model.get_db_provider(config)

    app.run(port=args.port, debug=True)


if __name__ == "__main__":
    main()
