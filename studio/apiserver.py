from flask import Flask, request, redirect
import json
import logging
import time

import model

logging.basicConfig()

app = Flask(__name__)
logger = logging.getLogger('apiserver')
logger.setLevel(10)

_my_db_provider = None


@app.route('/get_experiment', methods=['POST'])
def get_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Getting experiment {} '.format(key))
    try:
        experiment = get_db().get_experiment(key).__dict__
        status = 'ok'
    except BaseException as e:
        experiment = {}
        status = e.msg

    toc = time.time()
    logger.info('Processed get_experiment request in {} s'
        .format(toc - tic))

    return json.dumps({'status':status, 'experiment':{}})


@app.route('/get_user_experiments', methods=['POST'])
def get_user_experiments():
    tic = time.time()
    user = request.json['user']
    logger.info('Getting experiments of user {}'
        .format(user))

    experiments = get_db().get_user_experiments(user)
    toc = time.time()
    logger.info('Processed get_user_experiment request in {} s'
        .format(toc - tic))
    return json.dumps([e.__dict__ for e in experiments])

@app.route('/stop_experiment', methods=['POST'])
def stop_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Getting experiment {} '.format(key))
    try:
        experiment = get_db().stop_experiment(key)
        status = 'ok'
    except BaseException as e:
        status = e.msg

    toc = time.time()
    logger.info('Processed stop_experiment request in {} s'
        .format(toc - tic))

    return json.dumps({'status':status})


@app.route('/delete_experiment', methods=['POST'])
def stop_experiment():
    tic = time.time()
    key = request.json['key']
    logger.info('Getting experiment {} '.format(key))
    try:
        experiment = get_db().stop_experiment(key)
        status = 'ok'
    except BaseException as e:
        status = e.msg

    toc = time.time()
    logger.info('Processed delete_experiment request in {} s'
        .format(toc - tic))

    return json.dumps({'status':status})




def get_db():
    global _my_db_provider
    if not _my_db_provider:
        _my_db_provider = model.get_db_provider()

    return _my_db_provider


def main():
    app.run(host='0.0.0.0', debug=True)


if __name__ == '__main__':
    main()

