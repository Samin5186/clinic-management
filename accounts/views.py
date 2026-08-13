from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from .models import User, Doctor, Patient, Appointment, Medication, HealthReading


def home(request):
    return render(request, 'home.html')


def select_role(request):
    return render(request, 'select_role.html')


def login_view(request):
    role = request.GET.get('role', '')

    if request.method == 'POST':
        role = request.POST.get('role', '')

        if role == 'doctor':
            name = request.POST.get('name', '').strip()
            medical_number = request.POST.get('medical_number', '').strip()

            if not name or not medical_number:
                messages.error(request, 'Please fill in all fields.')
                return render(request, 'login.html', {'role': role})

            if len(medical_number) != 4 or not medical_number.isdigit():
                messages.error(request, 'Medical number must be exactly 4 digits.')
                return render(request, 'login.html', {'role': role})

            try:
                doctor = Doctor.objects.get(medical_number=medical_number)
                if doctor.name.strip().lower() == name.strip().lower():
                    login(request, doctor.user)
                    return redirect('doctor_appointments')
                else:
                    messages.error(request, 'Name does not match the medical number.')
            except Doctor.DoesNotExist:
                messages.error(request, 'Doctor not found with this medical number.')

        elif role == 'patient':
            identifier = request.POST.get('identifier', '').strip()
            password = request.POST.get('password', '').strip()

            if not identifier or not password:
                messages.error(request, 'Please fill in all fields.')
                return render(request, 'login.html', {'role': role})

            if len(password) != 5 or not password.isdigit():
                messages.error(request, 'Password must be exactly 5 digits.')
                return render(request, 'login.html', {'role': role})

            patients = Patient.objects.all()
            matched_patient = None
            for p in patients:
                if p.phone == identifier or p.email == identifier:
                    if p.password_5digit == password:
                        matched_patient = p
                        break

            if matched_patient:
                login(request, matched_patient.user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid phone/email or password.')

        elif role == 'admin':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()

            if not username or not password:
                messages.error(request, 'Please fill in all fields.')
                return render(request, 'login.html', {'role': role})

            user = authenticate(request, username=username, password=password)
            if user and user.is_admin_user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid admin credentials.')

        return render(request, 'login.html', {'role': role})

    return render(request, 'login.html', {'role': role})


def register_patient(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        age = request.POST.get('age', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        insurance = request.POST.get('insurance', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errors = []

        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        if not age or not age.isdigit() or int(age) <= 0:
            errors.append('Valid age is required.')
        if not phone or len(phone) != 11 or not phone.startswith('09') or not phone.isdigit():
            errors.append('Phone must be 11 digits starting with 09.')
        if not email or '@' not in email:
            errors.append('Valid email is required.')
        if len(password1) != 5 or not password1.isdigit():
            errors.append('Password must be exactly 5 digits.')
        if password1 != password2:
            errors.append('Passwords do not match.')

        if not errors:
            for p in Patient.objects.all():
                if p.phone == phone:
                    errors.append('This phone number is already registered.')
                    break
                if p.email == email:
                    errors.append('This email is already registered.')
                    break

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'insurance_choices': Patient.INSURANCE_CHOICES,
                'form_data': request.POST,
            })

        user = User.objects.create_user(
            username=email,
            password=password1,
            role='patient'
        )

        patient = Patient(
            user=user,
            age=int(age),
            password_5digit=password1,
            insurance=insurance
        )
        patient.first_name = first_name
        patient.last_name = last_name
        patient.phone = phone
        patient.email = email
        patient.save()

        login(request, user)
        messages.success(request, 'Registration successful! Welcome!')
        return redirect('home')

    return render(request, 'register.html', {'insurance_choices': Patient.INSURANCE_CHOICES})


def logout_view(request):
    logout(request)
    return redirect('home')


# ==================== Patient Appointment Views ====================

@login_required
def patient_appointments(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    appointments = Appointment.objects.filter(patient=patient, is_cancelled=False).order_by('year', 'month', 'day', 'hour')
    cancelled = Appointment.objects.filter(patient=patient, is_cancelled=True).order_by('-year', '-month', '-day', '-hour')[:10]

    return render(request, 'appointments/patient_appointments.html', {
        'patient': patient,
        'appointments': appointments,
        'cancelled': cancelled,
    })


@login_required
def appointment_book(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    doctors = Doctor.objects.all()
    selected_doctor = None
    booked_hours = []

    now = timezone.now()
    selected_day = now.day
    selected_month = now.month
    selected_year = now.year

    doctor_id = request.GET.get('doctor_id')
    day = request.GET.get('day')
    month = request.GET.get('month')
    year = request.GET.get('year')

    if day and month and year:
        selected_day = int(day)
        selected_month = int(month)
        selected_year = int(year)

    if doctor_id:
        selected_doctor = get_object_or_404(Doctor, id=doctor_id)
        booked_appointments = Appointment.objects.filter(
            doctor=selected_doctor,
            day=selected_day,
            month=selected_month,
            year=selected_year,
            is_cancelled=False
        )
        booked_hours = [a.hour for a in booked_appointments]

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        day = int(request.POST.get('day'))
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        hour = int(request.POST.get('hour'))
        reason = request.POST.get('reason', '').strip()

        doctor = get_object_or_404(Doctor, id=doctor_id)

        if hour < 8 or hour > 17:
            messages.error(request, 'Please select a time between 8 AM and 6 PM.')
        elif Appointment.objects.filter(
            doctor=doctor,
            day=day,
            month=month,
            year=year,
            hour=hour,
            is_cancelled=False
        ).exists():
            messages.error(request, 'The selected time is already booked.')
        else:
            appointment = Appointment(
                doctor=doctor,
                patient=patient,
                patient_name=patient.full_name,
                patient_phone=patient.phone,
                reason=reason,
                day=day,
                month=month,
                year=year,
                hour=hour,
            )
            appointment.save()
            messages.success(request, 'Appointment booked successfully!')
            return redirect('patient_appointments')

    return render(request, 'appointments/book_appointment.html', {
        'patient': patient,
        'doctors': doctors,
        'selected_doctor': selected_doctor,
        'booked_hours': booked_hours,
        'selected_day': selected_day,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'hours': range(8, 18),
    })


@login_required
def appointment_cancel(request, appointment_id):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)
    appointment.is_cancelled = True
    appointment.save()
    messages.success(request, 'Appointment cancelled successfully.')
    return redirect('patient_appointments')


@login_required
def appointment_delete(request, appointment_id):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)
    appointment.delete()
    messages.success(request, 'Appointment deleted permanently.')
    return redirect('patient_appointments')


# ==================== Doctor Appointment Views ====================

@login_required
def doctor_appointments(request):
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    doctor = request.user.doctor_profile
    appointments = Appointment.objects.filter(doctor=doctor, is_cancelled=False).order_by('year', 'month', 'day', 'hour')

    return render(request, 'appointments/doctor_appointments.html', {
        'doctor': doctor,
        'appointments': appointments,
    })


# ==================== Admin Views ====================

@login_required
def admin_panel(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('home')

    doctors = Doctor.objects.all()
    appointments = Appointment.objects.filter(is_cancelled=False).order_by('year', 'month', 'day', 'hour')
    regular_users = User.objects.filter(is_admin_user=False)
    admin_users = User.objects.filter(is_admin_user=True).exclude(username='sam')

    return render(request, 'admin/dashboard.html', {
        'doctors': doctors,
        'appointments': appointments,
        'regular_users': regular_users,
        'admin_users': admin_users,
    })


@login_required
def admin_add_doctor(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('home')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        medical_number = request.POST.get('medical_number', '').strip()

        errors = []
        if not name:
            errors.append('Doctor name is required.')
        if not medical_number or len(medical_number) != 4 or not medical_number.isdigit():
            errors.append('Medical number must be exactly 4 digits.')
        if Doctor.objects.filter(medical_number=medical_number).exists():
            errors.append('This medical number already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(
                username=f"dr_{medical_number}",
                password=medical_number,
                role='doctor'
            )
            doctor = Doctor(user=user, medical_number=medical_number)
            doctor.name = name
            doctor.save()
            messages.success(request, f'Dr. {name} added successfully!')
            return redirect('admin_panel')

    return render(request, 'admin/add_doctor.html')


@login_required
def admin_promote_user(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('home')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')

        try:
            user = User.objects.get(id=user_id, is_admin_user=False)
            user.is_admin_user = True
            user.role = 'admin'
            user.save()
            messages.success(request, f'{user.username} has been promoted to admin!')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')

        return redirect('admin_panel')

    regular_users = User.objects.filter(is_admin_user=False)
    return render(request, 'admin/promote_user.html', {'regular_users': regular_users})


@login_required
def admin_demote_user(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('home')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')

        try:
            user = User.objects.get(id=user_id, is_admin_user=True)
            if user.username == 'sam':
                messages.error(request, 'Cannot remove the main admin.')
            else:
                user.is_admin_user = False
                user.role = 'patient'
                user.save()
                messages.success(request, f'{user.username} has been removed from admin.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')

        return redirect('admin_panel')

    return redirect('admin_panel')


@login_required
def admin_remove_user(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Access denied. Admins only.')
        return redirect('home')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')

        try:
            user = User.objects.get(id=user_id, is_admin_user=False)
            if user.username == 'sam':
                messages.error(request, 'Cannot remove the main admin.')
            else:
                username = user.username
                user.delete()
                messages.success(request, f'User "{username}" removed from the site.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')

        return redirect('admin_panel')

    return redirect('admin_panel')


# ==================== Medication Views ====================

@login_required
def medication_list(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    medications = Medication.objects.filter(patient=patient).order_by('time')

    return render(request, 'medications/medication_list.html', {
        'patient': patient,
        'medications': medications,
        'days': Medication.DAYS_OF_WEEK,
    })


@login_required
def medication_add(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        dosage = request.POST.get('dosage', '').strip()
        time_str = request.POST.get('time', '').strip()
        times_per_day = int(request.POST.get('times_per_day', 1))
        days_list = request.POST.getlist('days_of_week')
        days_str = ','.join(days_list)

        errors = []
        if not name:
            errors.append('Medication name is required.')
        if not dosage:
            errors.append('Dosage is required.')
        if not time_str:
            errors.append('Time is required.')
        if not days_list:
            errors.append('Please select at least one day.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                hour, minute = map(int, time_str.split(':'))
                from datetime import time as dt_time
                from django.utils import timezone
                now = timezone.now()
                med = Medication(
                    patient=patient,
                    time=dt_time(hour, minute),
                    times_per_day=times_per_day,
                    days_of_week=days_str,
                    hour=hour,
                    day=now.day,
                    month=now.month,
                    year=now.year,
                )
                med.name = name
                med.dosage = dosage
                med.save()
                messages.success(request, 'Medication added successfully!')
                return redirect('medication_list')
            except ValueError:
                messages.error(request, 'Invalid time format. Use HH:MM.')

    return render(request, 'medications/medication_add.html', {
        'patient': patient,
        'days': Medication.DAYS_OF_WEEK,
    })


@login_required
def medication_delete(request, med_id):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    med = get_object_or_404(Medication, id=med_id, patient=patient)
    med.delete()
    messages.success(request, 'Medication deleted.')
    return redirect('medication_list')


@login_required
def medication_toggle_taken(request, med_id):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    med = get_object_or_404(Medication, id=med_id, patient=patient)
    day = request.GET.get('day', '')
    taken_days = (med.taken_days or '').split(',')
    if day in taken_days:
        taken_days.remove(day)
    elif day:
        taken_days.append(day)
    med.taken_days = ','.join(d for d in taken_days if d)
    med.save()
    return redirect('medication_by_day' + (f'?day={day}' if day else ''))


@login_required
def medication_by_day(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    selected_day = request.GET.get('day', '')
    medications = []

    if selected_day:
        all_meds = Medication.objects.filter(patient=patient).order_by('time')
        medications = [m for m in all_meds if selected_day in m.days_of_week.split(',')]
        for m in medications:
            m.is_taken = selected_day in (m.taken_days.split(',') if m.taken_days else [])
            m.toggle_url = f"{reverse('medication_toggle_taken', args=[m.id])}?day={selected_day}"

    return render(request, 'medications/medication_by_day.html', {
        'patient': patient,
        'medications': medications,
        'selected_day': selected_day,
        'days': Medication.DAYS_OF_WEEK,
    })


# ==================== Health Views ====================

@login_required
def health_dashboard(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    readings = HealthReading.objects.filter(patient=patient).order_by('-year', '-month', '-day', '-hour')

    return render(request, 'health/dashboard.html', {
        'patient': patient,
        'readings': readings,
    })


@login_required
def health_add(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile

    if request.method == 'POST':
        reading_type = request.POST.get('reading_type', '').strip()
        systolic = request.POST.get('systolic', '0').strip()
        diastolic = request.POST.get('diastolic', '0').strip()
        value = request.POST.get('value', '0').strip()

        from django.utils import timezone
        now = timezone.now()

        errors = []
        if not reading_type:
            errors.append('Reading type is required.')

        if reading_type == 'blood_pressure':
            if not systolic or not diastolic:
                errors.append('Both systolic and diastolic values are required.')
            else:
                try:
                    systolic = int(systolic)
                    diastolic = int(diastolic)
                except ValueError:
                    errors.append('Invalid blood pressure values.')
        else:
            if not value:
                errors.append('Value is required.')
            else:
                try:
                    value = int(value)
                except ValueError:
                    errors.append('Invalid value.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            reading = HealthReading(
                patient=patient,
                reading_type=reading_type,
                systolic=int(systolic) if systolic else 0,
                diastolic=int(diastolic) if diastolic else 0,
                value=int(value) if value else 0,
                hour=now.hour,
                day=now.day,
                month=now.month,
                year=now.year,
            )
            reading.save()
            messages.success(request, 'Health reading added successfully!')
            return redirect('health_dashboard')

    return render(request, 'health/add_reading.html', {
        'patient': patient,
        'types': HealthReading.READING_TYPES,
    })


@login_required
def health_delete(request, reading_id):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    reading = get_object_or_404(HealthReading, id=reading_id, patient=patient)
    reading.delete()
    messages.success(request, 'Health reading deleted.')
    return redirect('health_dashboard')


@login_required
def health_chart(request):
    if not hasattr(request.user, 'patient_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    readings = HealthReading.objects.filter(patient=patient).order_by('year', 'month', 'day', 'hour')

    return render(request, 'health/chart.html', {
        'patient': patient,
        'readings': readings,
    })
