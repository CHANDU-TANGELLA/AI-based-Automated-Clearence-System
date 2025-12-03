from django.db import models

class Student(models.Model):
    student_id = models.CharField(max_length=50, primary_key=True)
    student_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, default='Male')
    password = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    contact = models.CharField(max_length=20, db_column='contact_no')
    address = models.CharField(max_length=200, default='')
    course = models.CharField(max_length=50)
    course_year = models.CharField(max_length=20)
    
    # Fee fields (defaulting to 0)
    library_fee = models.FloatField(default=0.0)
    hostel_fee = models.FloatField(default=0.0)
    tution_fee = models.FloatField(default=0.0)
    exam_fee = models.FloatField(default=0.0)
    lab_hod_fee = models.FloatField(default=0.0)

    class Meta:
        db_table = 'student'
        unique_together = (('student_id', 'course_year'),)

class Employee(models.Model):
    emp_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    contact_no = models.CharField(max_length=20)
    email = models.EmailField(max_length=100)
    qualification = models.CharField(max_length=100)
    experience = models.CharField(max_length=50)
    user_role = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True, primary_key=True)
    password = models.CharField(max_length=100)

    class Meta:
        db_table = 'employees'

class Payment(models.Model):
    student_id = models.CharField(max_length=50)
    course_year = models.CharField(max_length=20)
    paying_dept = models.CharField(max_length=50)
    amount = models.FloatField()
    payment_date = models.CharField(max_length=50) 

    class Meta:
        db_table = 'payments'

class DocumentSubmission(models.Model):
    student_id = models.CharField(max_length=50)
    department = models.CharField(max_length=50)
    document_type = models.CharField(max_length=50, default='Unknown')
    file_path = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    ai_verification_status = models.CharField(max_length=20, default='Pending')
    ai_confidence_score = models.FloatField(default=0.0)

    class Meta:
        db_table = 'document_submissions'