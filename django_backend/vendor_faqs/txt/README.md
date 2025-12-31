This is a minimal Django app `vendor_faqs` that provides models and endpoints to support vendor CSV uploads and ingestion.

Suggested integration steps:

1. Add `vendor_faqs` to your Django `INSTALLED_APPS`.
2. Run `python manage.py makemigrations vendor_faqs` and `python manage.py migrate`.
3. Configure media storage (`MEDIA_ROOT`, `MEDIA_URL`) or use S3 via `django-storages`.
4. Install and configure Celery. The task `ingest_vendor_csv_task` is a scaffold — replace the placeholder with your Chroma ingestion call (e.g., call the `ingest_faq_data(path, vendor_id)` function from your Streamlit code or a shared library).
5. Endpoints provided:
   - `POST /api/vendors/{vendor_id}/csv-uploads/` -> upload CSV
   - `GET /api/vendors/{vendor_id}/csv-uploads/{upload_id}/status/` -> upload status
   - `POST /api/vendors/{vendor_id}/faqs/ingest/` -> trigger ingestion (optional `upload_id` in JSON)
   - `GET /api/vendors/{vendor_id}/faqs/` -> fetch raw FAQ rows from latest upload

Security and notes:
- Protect API endpoints with authentication (Token, JWT, or session) and validate vendor ownership.
- For production, ingestion should write directly to your vector DB (Chroma) with a vendor-scoped collection name (`faqs_vendor_{vendor_id}`).
- Add file size limits and CSV schema validation in `CSVUploadView` or via a serializer.
