#!/usr/bin/env bash

APP_ROOT=$(dirname $(dirname $(readlink -fm $0)))
pep8 --show-source --statistics $APP_ROOT
# find $APP_ROOT -name "*.py" -exec pep8 --show-source {} \;
