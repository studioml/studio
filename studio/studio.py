from flask import Flask, render_template

app = Flask(__name__)

import model

db_provider = model.get_db_provider()


@app.route('/')
def dashboard():
    experiments = db_provider.get_user_experiments()
    userid = db_provider.get_myuser_id()
    return render_template("dashboard.html", userid=userid, experiments=experiments)


@app.route('/experiment/<user>/<key>')
def experiment(user,key):
    experiment = db_provider.get_experiment(key, user_id=user)
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
    return render_template("project_details.html", project_name=key, project_dict=projects[key])

@app.route('/users')
def users():
    users = db_provider.get_users()
    return render_template("users.html", users=users)

@app.route('/user/<key>')
def user_experiments(key):
    experiments = db_provider.get_user_experiments(key)
    users = db_provider.get_users()
    email = users[key]['email'] if 'email' in users[key].keys() else None
    return render_template("user_details.html", user=key, email=email, experiments=experiments)

def main():
    app.run(debug=True)

if __name__ == "__main__":
    main()
