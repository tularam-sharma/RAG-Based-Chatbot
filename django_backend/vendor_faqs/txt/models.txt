from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class VendorCSVUpload(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='uploads')
    file = models.FileField(upload_to='vendor_uploads/%Y/%m/')
    filename = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name
        super().save(*args, **kwargs)


class VendorIngestionTask(models.Model):
    upload = models.ForeignKey(VendorCSVUpload, on_delete=models.CASCADE, related_name='ingestion_tasks')
    celery_task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, default='created')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"IngestTask(upload={self.upload_id}, status={self.status})"
