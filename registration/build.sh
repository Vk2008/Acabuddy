#!/usr/bin/env bash
# exit on error
set -o errexit

# Install the slimmed-down requirements
pip install -r requirements.txt

# Convert static files (CSS/Images) for WhiteNoise
python manage.py collectstatic --no-input

# Update the PostgreSQL database schema
python manage.py migrate