rm -rf lib
pip install -t lib -r ../requirements.txt
rm lib/tensorflow/python/_pywrap_tensorflow_internal.so
echo "" >  lib/tensorflow/__init__.py


# dev_appserver.py app.yaml
gcloud app deploy
