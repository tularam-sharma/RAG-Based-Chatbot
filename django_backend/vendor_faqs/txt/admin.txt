from django.contrib import admin
from .models import Vendor, VendorCSVUpload, VendorIngestionTask

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')


@admin.register(VendorCSVUpload)
class VendorCSVUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'vendor', 'filename', 'status', 'created_at')
    list_filter = ('status', 'vendor')


@admin.register(VendorIngestionTask)
class VendorIngestionTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'upload', 'status', 'started_at', 'finished_at')
