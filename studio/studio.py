from flask import Flask, render_template

app = Flask(__name__)

import model


@app.route('/')
def dashboard():
    db_provider = model.get_db_provider()
    experiments = db_provider.get_user_experiments('me')
    return render_template("dashboard.html", experiments=experiments)


@app.route('/experiment/<key>')
def experiment(key):
    db_provider = model.get_db_provider()
    experiment = db_provider.get_experiment(key)
    return render_template("experiment_details.html", experiment=experiment)

@app.route('/auth')
def auth():
    #db_provider = model.get_db_provider()
    #experiments = db_provider.get_user_experiments('me')
    return render_template("auth.html")



def main():
    app.run(debug=True)

if __name__ == "__main__":
    main()
