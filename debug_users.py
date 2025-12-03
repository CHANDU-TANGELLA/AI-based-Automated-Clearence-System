import os
import django
import sys

print("Starting debug script...", flush=True)

try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "NoDue.settings")
    django.setup()
    print("Django setup complete.", flush=True)

    from NoDueApp.models import Employee

    print("Checking Employees...", flush=True)
    employees = Employee.objects.all()
    print(f"Found {len(employees)} employees.", flush=True)
    for emp in employees:
        print(f"User: {emp.username}, Pass: {emp.password}, Role: {emp.user_role}", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)
