from django.core.management.base import BaseCommand
from accounts.models import Doctor, Patient, Medication, Appointment, HealthReading, User


class Command(BaseCommand):
    help = 'Delete all non-admin data'

    def handle(self, *args, **options):
        HealthReading.objects.all().delete()
        Appointment.objects.all().delete()
        Medication.objects.all().delete()
        Patient.objects.all().delete()
        Doctor.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.SUCCESS('All non-admin data deleted'))
