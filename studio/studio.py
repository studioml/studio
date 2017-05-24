from flask import Flask, render_template

app = Flask(__name__)

import model


@app.route('/')
def dashboard():
    db_provider = model.get_db_provider()
    experiments = db_provider.get_user_experiments()
    return render_template("dashboard.html", experiments=experiments)


@app.route('/experiment/<key>')
def experiment(key):
    db_provider = model.get_db_provider()
    experiment = db_provider.get_experiment(key)
    return render_template("experiment_details.html", experiment=experiment)

@app.route('/projects')
def projects():
    db_provider = model.get_db_provider()
    projects = db_provider.get_projects()
    return render_template("projects.html", projects=projects)

@app.route('/project/<key>')
def project_details(key):
    db_provider = model.get_db_provider()
    projects = db_provider.get_projects()

    return render_template("project_details.html", project_name=key, project_dict=projects[key])




def main():
    app.run(debug=True)

if __name__ == "__main__":
    main()
