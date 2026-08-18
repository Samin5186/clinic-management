from django.contrib import admin
from django.urls import path, include
from .views import custom_500

handler500 = custom_500

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
]
