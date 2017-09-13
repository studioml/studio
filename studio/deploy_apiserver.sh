if [[ -z "$FIREBASE_ADMIN_CREDENTIALS" ]]; then
    echo "*** Firbase admin credentials file reqiured! ***"
    echo "*** Set path to credentials json in FIREBASE_ADMIN_CREDENTIALS env variable ***"
    exit 1
fi

creds="./firebase_admin_creds.json"
cp $FIREBASE_ADMIN_CREDENTIALS $creds

if [ "$1" = "gae" ]; then

    
    mv default_config.yaml default_config.yaml.orig
    cp apiserver_config.yaml default_config.yaml

    rm -rf lib
    pip install -t lib -r ../requirements.txt
    rm lib/tensorflow/python/_pywrap_tensorflow_internal.so
    echo "" >  lib/tensorflow/__init__.py

    # dev_appserver.py app.yaml --dev_appserver_log_level debug
    yes Y | gcloud app deploy

    mv default_config.yaml.orig default_config.yaml
else if [ "$1" = "local" ]; then
        port=$2
        studio ui --config=apiserver_config.yaml --port=$port
    else
        echo "*** unknown target: $1"
        exit 1
    fi
fi

rm -f $creds
