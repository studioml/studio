import time
from flask import Flask, render_template
import model

app = Flask(__name__)


db_provider = model.get_db_provider()


@app.template_filter('format_time')
def format_time(timestamp):
    return time.strftime(
        '%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@app.route('/')
def dashboard():
    experiments = db_provider.get_user_experiments()
    return render_template("dashboard.html", experiments=experiments)


@app.route('/experiments/<key>')
def experiment(key):
    experiment = db_provider.get_experiment(key)
    return render_template("experiment_details.html", experiment=experiment)


@app.route('/projects')
def projects():
    projects = db_provider.get_projects()
    if not projects:
        projects = {}
    return render_template("projects.html", projects=projects)


@app.route('/project/<key>')
def project_details(key):
    projects = db_provider.get_projects()
    return render_template(
        "project_details.html",
        project_name=key,
        project_dict=projects[key])



@app.route('/users')
def users():
    users = db_provider.get_users()
    return render_template("users.html", users=users)


@app.route('/user/<key>')
def user_experiments(key):
    experiments = db_provider.get_user_experiments(key)
    users = db_provider.get_users()
    email = users[key]['email'] if 'email' in users[key].keys() else None
    return render_template(
        "user_details.html",
        user=key,
        email=email,
        experiments=experiments)



def main():
    app.run(debug=True)


if __name__ == "__main__":
    main()
