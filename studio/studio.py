import time
from flask import Flask, render_template
import model
import argparse
import yaml

app = Flask(__name__)


_db_provider = None


@app.template_filter('format_time')
def format_time(timestamp):
    return time.strftime(
        '%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@app.route('/')
def dashboard():
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
    parser.add_argument('--guest',
                        help='Guest mode (does not require db credentials)',
                        action='store_true')

    parser.add_argument('--port', 
                        help='port to run Flask server on',
                        type=int,
                        default=5000)

    args = parser.parse_args()
    config = model.get_default_config()
    if args.config:
        with open(args.config) as f:
            config.update(yaml.load(f))

    if args.guest:
        config['database']['guest'] = True

    global _db_provider
    _db_provider = model.get_db_provider(config)

    app.run(port=args.port, debug=True)


if __name__ == "__main__":
    main()
