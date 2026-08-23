from django.conf import settings


def google_oauth(request):
    app = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {})
    return {'google_enabled': bool(app.get('client_id') and app.get('secret'))}
