from django.contrib import admin
from .models import User, Doctor, Patient

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'role', 'is_admin_user']

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['medical_number']

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['insurance']
