#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.prod.txt

python manage.py check
python manage.py collectstatic --noinput
