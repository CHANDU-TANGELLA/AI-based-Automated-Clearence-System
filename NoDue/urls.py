from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('NoDueApp.urls')), # This correctly links to your app's urls.py
]