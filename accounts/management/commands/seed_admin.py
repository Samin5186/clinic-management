import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the main clinic admin user if it does not exist.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('ADMIN_USERNAME', 'sam')
        password = os.environ.get('ADMIN_PASSWORD', 'sam@5186')

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.SUCCESS(f'Admin "{username}" already exists.'))
            return

        User.objects.create_superuser(
            username=username,
            password=password,
            role='admin',
            is_admin_user=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Admin "{username}" created.'))
