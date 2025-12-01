from django.db import models

class DocumentSubmission(models.Model):
    student_id = models.CharField(max_length=50)
    department = models.CharField(max_length=50)
    document_type = models.CharField(max_length=50)
    file_path = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    ai_verification_status = models.CharField(max_length=20, default='Pending')
    ai_confidence_score = models.FloatField(default=0.0)

    class Meta:
        db_table = 'document_submissions'