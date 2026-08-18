from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.urls import reverse
from datetime import date, timedelta
from .models import User, Doctor, Patient, Appointment, Medication, HealthReading


def home(request):
    if request.user.is_authenticated:
        if request.user.role == 'patient':
            return redirect('patient_dashboard')
        elif request.user.role == 'doctor':
            return redirect('doctor_appointments')
        elif request.user.is_admin_user:
            return redirect('admin_panel')
        return redirect('patient_dashboard')
    return render(request, 'landing.html')


@login_required
def patient_dashboard(request):
    if request.user.role != 'patient':
        return redirect('home')

    try:
        patient = request.user.patient_profile
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found. Please contact support.')
        return redirect('home')
    today = date.today()
    tomorrow = today + timedelta(days=1)
    weekday_map = {0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday'}
    today_name = weekday_map[today.weekday()]

    meds_today = Medication.objects.filter(patient=patient, days_of_week__contains=today_name)
    reminders = []
    for med in meds_today:
        taken = (med.taken_days or '').split(',')
        if today_name not in taken:
            reminders.append({'type': 'medication', 'message': f"Time to take {med.name} ({med.dosage})", 'med': med})

    upcoming_appts = Appointment.objects.filter(
        patient=patient, is_cancelled=False,
        year=tomorrow.year, month=tomorrow.month, day=tomorrow.day,
    )
    for appt in upcoming_appts:
        reminders.append({'type': 'appointment', 'message': f"Appointment with Dr. {appt.doctor.name} tomorrow at {appt.hour:02d}:{appt.minute:02d}", 'appt': appt})

    return render(request, 'patient_dashboard.html', {
        'reminders': reminders,
        'reminder_count': len(reminders),
        'reminders_json': [{'type': r['type'], 'message': r['message']} for r in reminders],
    })


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('home')
    if request.user.role == 'patient':
        return redirect('patient_dashboard')
    elif request.user.role == 'doctor':
        return redirect('doctor_appointments')
    elif request.user.is_admin_user:
        return redirect('admin_panel')
    return redirect('home')


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html')

        # Try admin login first (username + password)
        user = authenticate(request, username=identifier, password=password)
        if user and user.is_admin_user:
            login(request, user)
            return redirect('admin_panel')

        # Try doctor login (username or name, password = medical_number)
        try:
            doctor = Doctor.objects.get(user__username=identifier)
            if doctor.user.check_password(password):
                login(request, doctor.user)
                return redirect('doctor_appointments')
        except Doctor.DoesNotExist:
            pass

        try:
            doctor = Doctor.objects.get(name__iexact=identifier)
            if doctor.user.check_password(password):
                login(request, doctor.user)
                return redirect('doctor_appointments')
        except Doctor.DoesNotExist:
            pass

        # Try patient login (email/phone/username + password)
        patients = Patient.objects.all()
        matched_patient = None
        for p in patients:
            if (p.email == identifier or p.phone == identifier or p.user.username == identifier) and check_password(password, p.password_hash):
                matched_patient = p
                break

        if matched_patient:
            login(request, matched_patient.user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('patient_dashboard')

        # Try admin with username (in case identifier is username)
        user = authenticate(request, username=identifier, password=password)
        if user and user.is_admin_user:
            login(request, user)
            return redirect('admin_panel')

        messages.error(request, 'Invalid credentials. Please check your credentials and try again.')
        return render(request, 'login.html')

    return render(request, 'login.html')


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
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters long.')
        if password1.isalpha():
            errors.append('Password must contain at least one number.')
        if password1.isdigit():
            errors.append('Password must contain at least one letter.')
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

        base_username = first_name.lower().replace(' ', '')
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            password=password1,
            role='patient'
        )

        patient = Patient(
            user=user,
            age=int(age),
            password_hash=make_password(password1),
            insurance=insurance
        )
        patient.first_name = first_name
        patient.last_name = last_name
        patient.phone = phone
        patient.email = email
        patient.save()

        login(request, user)
        messages.success(request, f'Registration successful! Your username is "{username}". Welcome!')
        return redirect('patient_dashboard')

    return render(request, 'register.html', {'insurance_choices': Patient.INSURANCE_CHOICES})


def logout_view(request):
    logout(request)
    return redirect('home')


# ==================== Patient Appointment Views ====================

@login_required
def patient_appointments(request):
    try:
        patient = request.user.patient_profile
    except Patient.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('home')
    appointments = Appointment.objects.filter(patient=patient, is_cancelled=False).order_by('year', 'month', 'day', 'hour')
    cancelled = Appointment.objects.filter(patient=patient, is_cancelled=True).order_by('-year', '-month', '-day', '-hour')[:10]

    return render(request, 'appointments/patient_appointments.html', {
        'patient': patient,
        'appointments': appointments,
        'cancelled': cancelled,
    })


@login_required
def appointment_book(request):
    try:
        patient = request.user.patient_profile
    except Patient.DoesNotExist:
        messages.error(request, 'Access denied.')
        return redirect('home')

    patient = request.user.patient_profile
    doctors = Doctor.objects.all()
    selected_doctor = None
    booked_hours = []

    now = timezone.now()
    selected_day = None
    selected_month = now.month
    selected_year = now.year

    doctor_id = request.GET.get('doctor_id')
    day = request.GET.get('day')
    month = request.GET.get('month')
    year = request.GET.get('year')

    if month and year:
        selected_month = int(month)
        selected_year = int(year)

    if selected_month < 1:
        selected_month = 12
        selected_year -= 1
    elif selected_month > 12:
        selected_month = 1
        selected_year += 1

    if day:
        selected_day = int(day)

    if doctor_id:
        selected_doctor = get_object_or_404(Doctor, id=doctor_id)

        if selected_day is not None:
            booked_appointments = Appointment.objects.filter(
                doctor=selected_doctor,
                day=selected_day,
                month=selected_month,
                year=selected_year,
                is_cancelled=False
            )
            booked_hours = [a.hour for a in booked_appointments]

    import calendar as cal
    cal_obj = cal.Calendar(firstweekday=5)
    month_days = cal_obj.monthdayscalendar(selected_year, selected_month)
    month_name = cal.month_name[selected_month]

    if selected_month == 12:
        next_month, next_year = 1, selected_year + 1
    else:
        next_month, next_year = selected_month + 1, selected_year

    if selected_month == 1:
        prev_month, prev_year = 12, selected_year - 1
    else:
        prev_month, prev_year = selected_month - 1, selected_year

    calendar_weekdays = []
    for week in month_days:
        for d in week:
            if d == 0:
                continue
            try:
                dt = date(selected_year, selected_month, d)
                is_weekday = dt.weekday() not in (5, 6)
                is_past = dt < now.date()
                calendar_weekdays.append({
                    'day': d,
                    'weekday': dt.weekday(),
                    'name': cal.day_abbr[dt.weekday()],
                    'is_weekday': is_weekday,
                    'is_past': is_past,
                    'is_today': dt == now.date(),
                    'is_selected': selected_day == d,
                })
            except ValueError:
                pass

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        day = int(request.POST.get('day'))
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        hour = int(request.POST.get('hour'))
        reason = request.POST.get('reason', '').strip()

        doctor = get_object_or_404(Doctor, id=doctor_id)

        from datetime import date as dt_date
        try:
            check_date = dt_date(year, month, day)
            if check_date.weekday() in (5, 6):
                messages.error(request, 'Cannot book appointments on Saturday or Sunday.')
                return redirect(f"{request.path}?doctor_id={doctor_id}")
        except ValueError:
            pass

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
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'month_name': month_name,
        'month_days': month_days,
        'calendar_weekdays': calendar_weekdays,
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

from datetime import date as dt_date

@login_required
def doctor_appointments(request):
    if not hasattr(request.user, 'doctor_profile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    doctor = request.user.doctor_profile
    appointments = Appointment.objects.filter(doctor=doctor, is_cancelled=False).order_by('year', 'month', 'day', 'hour')

    grouped = {}
    day_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
    for appt in appointments:
        try:
            d = dt_date(appt.year, appt.month, appt.day)
            key = d.isoformat()
        except ValueError:
            key = f"{appt.year}-{appt.month:02d}-{appt.day:02d}"
            d = None

        if key not in grouped:
            if d:
                grouped[key] = {
                    'date': d,
                    'day_name': day_names.get(d.weekday(), ''),
                    'display': d.strftime('%b %d, %Y'),
                    'appointments': [],
                }
            else:
                grouped[key] = {
                    'date': None,
                    'day_name': '',
                    'display': f"{appt.year}/{appt.month}/{appt.day}",
                    'appointments': [],
                }

        try:
            patient = appt.patient
            insurance = patient.get_insurance_display_name()
        except Exception:
            insurance = 'Unknown'

        grouped[key]['appointments'].append({
            'patient_name': appt.patient_name,
            'patient_phone': appt.patient_phone,
            'time': f"{appt.hour:02d}:{appt.minute:02d}",
            'reason': appt.reason,
            'insurance': insurance,
        })

    sorted_days = sorted(grouped.values(), key=lambda x: x['date'] if x['date'] else dt_date.max)

    return render(request, 'appointments/doctor_appointments.html', {
        'doctor': doctor,
        'appointments': appointments,
        'grouped_days': sorted_days,
        'total_count': appointments.count(),
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
            base_username = name.lower().replace(' ', '')
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                password=medical_number,
                role='doctor'
            )
            doctor = Doctor(user=user, medical_number=medical_number)
            doctor.name = name
            doctor.save()
            messages.success(request, f'Dr. {name} added! Username: {username}')
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
        times_per_day = int(request.POST.get('times_per_day', 1))
        days_list = request.POST.getlist('days_of_week')
        days_str = ','.join(days_list)

        errors = []
        if not name:
            errors.append('Medication name is required.')
        if not dosage:
            errors.append('Dosage is required.')
        if not days_list:
            errors.append('Please select at least one day.')

        times_list = []
        for i in range(1, times_per_day + 1):
            t = request.POST.get(f'time_{i}', '').strip()
            if not t:
                errors.append(f'Time {i} is required.')
            else:
                times_list.append(t)

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                from datetime import time as dt_time
                from django.utils import timezone
                now = timezone.now()
                first_hour, first_minute = map(int, times_list[0].split(':'))
                times_str = ','.join(times_list)
                med = Medication(
                    patient=patient,
                    time=dt_time(first_hour, first_minute),
                    times_of_day=times_str,
                    times_per_day=times_per_day,
                    days_of_week=days_str,
                    hour=first_hour,
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
    day = request.GET.get('day') or request.POST.get('day', '')
    taken_days = (med.taken_days or '').split(',')
    if day in taken_days:
        taken_days.remove(day)
    elif day:
        taken_days.append(day)
    med.taken_days = ','.join(d for d in taken_days if d)
    med.save()
    url = reverse('medication_by_day')
    if day:
        url += f'?day={day}'
    return redirect(url)


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
