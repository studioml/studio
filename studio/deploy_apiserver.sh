#if [[ -z "$FIREBASE_ADMIN_CREDENTIALS" ]]; then
#    echo "*** Firbase admin credentials file reqiured! ***"
#    echo "Input path to firebase admin credentials json"
#    echo "(you can also set FIREBASE_ADMIN_CREDENTIALS env variable manually):"
#    read -p ">>" firebase_creds
#else
#    firebase_creds=$FIREBASE_ADMIN_CREDENTIALS
#fi

#if [ ! -f $firebase_creds ]; then
#   echo " *** File $firebase_creds does not exist! ***"
#   exit 1
#fi

#creds="./firebase_admin_creds.json"
#cp $firebase_creds $creds

if [ "$1" = "gae" ]; then

    mv default_config.yaml default_config.yaml.orig
    cp apiserver_config.yaml default_config.yaml

    rm -rf lib
    # pip install -t lib -r ../requirements.txt
    pip install -t lib ../
    rm lib/tensorflow/python/_pywrap_tensorflow_internal.so
    echo "" >  lib/tensorflow/__init__.py

    # dev_appserver.py app.yaml --dev_appserver_log_level debug
    yes Y | gcloud app deploy --no-promote

    mv default_config.yaml.orig default_config.yaml
else if [ "$1" = "local" ]; then
        port=$2
        studio ui --config=apiserver_config.yaml --port=$port
    else
        echo "*** unknown target: $1 (should be either gae or local) ***"
        exit 1
    fi
fi

# rm -f $creds
rm -rf lib
