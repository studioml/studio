#!/usr/bin/env bash

APP_ROOT=$(dirname $(dirname $(stat -fm $0)))
echo $APP_ROOT
pep8 --show-source --statistics $APP_ROOT
# find $APP_ROOT -name "*.py" -exec pep8 --show-source {} \;
