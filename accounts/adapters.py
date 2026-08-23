from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=False):
        user = super().save_user(request, user, form, commit=False)
        user.role = 'patient'
        user.is_admin_user = False

        base = (user.email or user.username or 'googleuser').split('@')[0]
        username = base[:140]
        suffix = 1
        while user.__class__.objects.filter(username=username).exclude(pk=user.pk).exists():
            username = f"{base[:130]}{suffix}"
            suffix += 1
        user.username = username

        user.save()
        return user

    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, 'role', '') == 'patient':
            if not hasattr(user, 'patient_profile'):
                return reverse('google_complete_profile')
        return super().get_login_redirect_url(request)
