from django.urls import path
from . import views

urlpatterns = [
    # Web UI endpoints
    path('', views.home, name='home'),
    path('vendors/', views.vendor_list_view, name='vendor_list_view'),
    path('upload/', views.csv_upload_view, name='csv_upload_view'),
    path('ingestion/', views.ingestion_status_view, name='ingestion_status_view'),
    path('chat/', views.chat_view, name='chat_view'),
    
    # API endpoints
    path('api/vendors/', views.VendorListCreateView.as_view(), name='vendor_list_create'),
    path('api/vendors/<int:vendor_id>/csv-uploads/', views.CSVUploadView.as_view(), name='csv_upload'),
    path('api/vendors/<int:vendor_id>/csv-uploads/<int:upload_id>/status/', views.UploadStatusView.as_view(), name='upload_status'),
    path('api/vendors/<int:vendor_id>/faqs/ingest/', views.TriggerIngestView.as_view(), name='trigger_ingest'),
    path('api/vendors/<int:vendor_id>/faqs/', views.FAQListView.as_view(), name='faq_list'),
]
