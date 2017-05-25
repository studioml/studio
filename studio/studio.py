from flask import Flask, render_template

app = Flask(__name__)

import model


@app.route('/')
def dashboard():
    db_provider = model.get_db_provider()
    experiments = db_provider.get_user_experiments()
    userid = db_provider.get_myuser_id()
    return render_template("dashboard.html", userid=userid, experiments=experiments)


@app.route('/experiment/<user>/<key>')
def experiment(user,key):
    db_provider = model.get_db_provider()
    experiment = db_provider.get_experiment(key, user_id=user)
    return render_template("experiment_details.html", experiment=experiment)

@app.route('/projects')
def projects():
    db_provider = model.get_db_provider()
    projects = db_provider.get_projects()
    if not projects:
        projects = {}
    return render_template("projects.html", projects=projects)

@app.route('/project/<key>')
def project_details(key):
    db_provider = model.get_db_provider()
    projects = db_provider.get_projects()
    return render_template("project_details.html", project_name=key, project_dict=projects[key])

@app.route('/users')
def users():
    db_provider = model.get_db_provider()
    users = db_provider.get_users()
    return render_template("users.html", users=users)

@app.route('/user/<key>')
def user_experiments(key):
    db_provider = model.get_db_provider()
    projects = db_provider.get_user_experiments(key)
    users = db_provider.get_users()
    return render_template("user_details.html", users=users, user=key)



def main():
    app.run(debug=True)

if __name__ == "__main__":
    main()
