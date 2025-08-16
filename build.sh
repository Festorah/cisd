#!/usr/bin/env bash
set -o errexit  # stop if any command fails

pip install -r requirements.txt
python manage.py migrate --noinput
# npx prisma migrate deploy
