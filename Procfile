web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py seed_admin && gunicorn clinic_auth.wsgi --bind 0.0.0.0:$PORT --workers 1 --timeout 30
