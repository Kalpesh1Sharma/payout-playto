#!/bin/bash
celery -A config worker --loglevel=info --concurrency=1 --detach
python manage.py migrate
python manage.py seed_merchants  
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
