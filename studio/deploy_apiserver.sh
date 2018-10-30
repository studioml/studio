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

config="apiserver_config.yaml"
if [ -n "$2" ]; then
    config=$2
fi

echo "config file = $config"

if [ "$1" = "gae" ]; then

    mv default_config.yaml default_config.yaml.orig
    cp $config default_config.yaml
    cp app.yaml app.yaml.old
    echo "env_variables:" >> app.yaml

    if [ -n "$AWS_ACCESS_KEY_ID" ]; then
        echo "exporting AWS env variables to app.yaml"
        echo "  AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID" >> app.yaml
        echo "  AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY" >> app.yaml
        echo "  AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION" >> app.yaml
    fi

    if [ -n "$STUDIO_GITHUB_ID" ]; then
        echo "exporting github secret env variables to app.yaml"
        echo "  STUDIO_GITHUB_ID: $STUDIO_GITHUB_ID" >> app.yaml
        echo "  STUDIO_GITHUB_SECRET: $STUDIO_GITHUB_SECRET" >> app.yaml
    fi

    rm -rf lib
    # pip install -t lib -r ../requirements.txt
    pip install -t lib ../
    # pip install -t lib -r ../extra_server_requirements.txt

    # patch library files where necessary
    for patch in $(find patches -name "*.patch"); do
        filename=${patch#patches/}
        filename=${filename%.patch}
        patch lib/$filename $patch
    done

    rm lib/tensorflow/python/_pywrap_tensorflow_internal.so
    echo "" >  lib/tensorflow/__init__.py

    # dev_appserver.py app.yaml --dev_appserver_log_level debug
    yes Y | gcloud app deploy --no-promote

    mv default_config.yaml.orig default_config.yaml
    mv app.yaml.old app.yaml
else if [ "$1" = "local" ]; then
        port=$2
        studio ui --config=apiserver_config.yaml --port=$port
    else
        echo "*** unknown target: $1 (should be either gae or local) ***"
        exit 1
    fi
fi

# rm -f $creds
# rm -rf lib
