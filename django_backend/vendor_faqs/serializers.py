from rest_framework import serializers
from .models import Vendor, VendorCSVUpload, VendorIngestionTask


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'name', 'slug']


class VendorCSVUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorCSVUpload
        fields = ['id', 'vendor', 'filename', 'file', 'status', 'created_at', 'updated_at', 'error_message']
        read_only_fields = ['status', 'created_at', 'updated_at', 'error_message']


class VendorIngestionTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorIngestionTask
        fields = ['id', 'upload', 'celery_task_id', 'status', 'started_at', 'finished_at', 'error_message']
        read_only_fields = ['celery_task_id', 'status', 'started_at', 'finished_at', 'error_message']
