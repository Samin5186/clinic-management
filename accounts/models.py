from django.db import models
from django.contrib.auth.models import AbstractUser
from .encryption import encrypt_data, decrypt_data

INSURANCE_CHOICES = [
    ('bimeh_salamat', 'Bimeh Salamat Iranian (Iran Health Insurance)'),
    ('bimeh_tamin_ejtemaei', 'Social Security Insurance'),
    ('bimeh_niroo_mosallah', 'Armed Forces Insurance'),
    ('bimeh_roostaei_ashayer', 'Rural & Nomadic Insurance'),
    ('bimeh_komite_emdad', 'Imam Khomeini Relief Committee Insurance'),
    ('bimeh_khadamat_darmani', 'Medical Services Insurance (Gov. Employees)'),
    ('bimeh_iran', 'Iran Insurance'),
    ('bimeh_asia', 'Asia Insurance'),
    ('bimeh_dana', 'Dana Insurance'),
    ('bimeh_parsian', 'Parsian Insurance'),
    ('bimeh_novin', 'Novin Insurance'),
    ('bimeh_saman', 'Saman Insurance'),
    ('bimeh_razi', 'Razi Insurance'),
]


class User(AbstractUser):
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')
    is_admin_user = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    name_encrypted = models.TextField()
    medical_number = models.CharField(max_length=4, unique=True)
    accepted_insurance = models.CharField(max_length=500, default='', blank=True, help_text='Comma-separated insurance keys the doctor accepts')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def name(self):
        return decrypt_data(self.name_encrypted)

    @name.setter
    def name(self, value):
        self.name_encrypted = encrypt_data(value)

    def get_accepted_insurance_list(self):
        if not self.accepted_insurance:
            return []
        return [i.strip() for i in self.accepted_insurance.split(',') if i.strip()]

    def get_accepted_insurance_display(self):
        choices = dict(INSURANCE_CHOICES)
        items = self.get_accepted_insurance_list()
        return ', '.join([choices.get(i, i) for i in items]) or 'No insurance set'

    def __str__(self):
        return f"Dr. {self.name} ({self.medical_number})"


class Patient(models.Model):
    INSURANCE_CHOICES = INSURANCE_CHOICES

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    first_name_encrypted = models.TextField()
    last_name_encrypted = models.TextField()
    age = models.IntegerField()
    phone_encrypted = models.TextField(unique=True)
    email_encrypted = models.TextField(unique=True)
    password_hash = models.CharField(max_length=128, default='')
    insurance = models.CharField(max_length=30, choices=INSURANCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def first_name(self):
        return decrypt_data(self.first_name_encrypted)

    @first_name.setter
    def first_name(self, value):
        self.first_name_encrypted = encrypt_data(value)

    @property
    def last_name(self):
        return decrypt_data(self.last_name_encrypted)

    @last_name.setter
    def last_name(self, value):
        self.last_name_encrypted = encrypt_data(value)

    @property
    def phone(self):
        return decrypt_data(self.phone_encrypted)

    @phone.setter
    def phone(self, value):
        self.phone_encrypted = encrypt_data(value)

    @property
    def email(self):
        return decrypt_data(self.email_encrypted)

    @email.setter
    def email(self, value):
        self.email_encrypted = encrypt_data(value)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_insurance_display_name(self):
        insurance_names = {
            'bimeh_salamat': 'Bimeh Salamat Iranian',
            'bimeh_tamin_ejtemaei': 'Bimeh Tamin Ejtemaei',
            'bimeh_niroo_mosallah': 'Bimeh Niroo Mosallah',
            'bimeh_roostaei_ashayer': 'Bimeh Roostaei va Ashayer',
            'bimeh_komite_emdad': 'Bimeh Komite Emdad Emam Khomeini',
            'bimeh_khadamat_darmani': 'Bimeh Khadamat Darmani Karkan Dolat',
            'bimeh_iran': 'Bimeh Iran',
            'bimeh_asia': 'Bimeh Asia',
            'bimeh_dana': 'Bimeh Dana',
            'bimeh_parsian': 'Bimeh Parsian',
            'bimeh_novin': 'Bimeh Novin',
            'bimeh_saman': 'Bimeh Saman',
            'bimeh_razi': 'Bimeh Razi',
        }
        if not self.insurance:
            return 'No Insurance'
        return insurance_names.get(self.insurance, self.insurance)

    def __str__(self):
        return self.full_name


class Appointment(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    patient_name = models.CharField(max_length=200)
    patient_phone = models.CharField(max_length=11)
    reason = models.TextField()
    day = models.IntegerField()
    month = models.IntegerField()
    year = models.IntegerField()
    hour = models.IntegerField()
    minute = models.IntegerField(default=0)
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr. {self.doctor.name} - {self.patient_name} ({self.year}/{self.month}/{self.day} {self.hour}:00)"


class Medication(models.Model):
    DAYS_OF_WEEK = [
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medications')
    name_encrypted = models.TextField()
    dosage_encrypted = models.TextField()
    time = models.TimeField()
    times_of_day = models.CharField(max_length=200, default='', blank=True, help_text='Comma-separated times like 08:00,14:00,20:00')
    times_per_day = models.IntegerField(default=1)
    days_of_week = models.CharField(max_length=100, default='')
    hour = models.IntegerField(default=8)
    day = models.IntegerField()
    month = models.IntegerField()
    year = models.IntegerField()
    taken_days = models.CharField(max_length=100, default='', blank=True, help_text='Comma-separated weekdays the dose was taken')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def name(self):
        return decrypt_data(self.name_encrypted)

    @name.setter
    def name(self, value):
        self.name_encrypted = encrypt_data(value)

    @property
    def dosage(self):
        return decrypt_data(self.dosage_encrypted)

    @dosage.setter
    def dosage(self, value):
        self.dosage_encrypted = encrypt_data(value)

    def get_days_display(self):
        day_names = {
            'saturday': 'Saturday',
            'sunday': 'Sunday',
            'monday': 'Monday',
            'tuesday': 'Tuesday',
            'wednesday': 'Wednesday',
            'thursday': 'Thursday',
            'friday': 'Friday',
        }
        days = self.days_of_week.split(',') if self.days_of_week else []
        if len(days) == 7:
            return 'Every day'
        return ', '.join([day_names.get(d, d) for d in days if d])

    def get_times_display(self):
        if self.times_of_day:
            return self.times_of_day
        return str(self.time)

    def __str__(self):
        return f"{self.name} - {self.patient.full_name}"


class HealthReading(models.Model):
    READING_TYPES = [
        ('blood_pressure', 'Blood Pressure'),
        ('blood_sugar', 'Blood Sugar'),
        ('heart_rate', 'Heart Rate'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='health_readings')
    reading_type = models.CharField(max_length=20, choices=READING_TYPES)
    systolic = models.IntegerField(default=0)
    diastolic = models.IntegerField(default=0)
    value = models.IntegerField(default=0)
    hour = models.IntegerField()
    day = models.IntegerField()
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.full_name} - {self.get_reading_type_display()} ({self.year}/{self.month}/{self.day})"
