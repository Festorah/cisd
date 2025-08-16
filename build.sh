#!/usr/bin/env bash
set -o errexit  # stop if any command fails

pip install -r requirements.txt
python manage.py migrate --noinput
# python manage.py setup_cisd_cms --sample-data
# npx prisma migrate deploy
