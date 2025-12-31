from celery import shared_task
from django.utils import timezone
from .models import VendorCSVUpload, VendorIngestionTask
import os
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions


def _collection_name_for_vendor(vendor_identifier) -> str:
    safe = str(vendor_identifier).replace(' ', '_')
    return f"faqs_vendor_{safe}"


@shared_task(bind=True)
def ingest_vendor_csv_task(self, upload_id: int, task_id: int):
    """Celery task to ingest vendor CSV into Chroma.

    Reads the uploaded CSV file path, validates columns, and writes embeddings
    into a vendor-scoped Chroma collection named `faqs_vendor_{vendor_id}`.
    """
    task = VendorIngestionTask.objects.get(pk=task_id)
    upload = VendorCSVUpload.objects.get(pk=upload_id)

    try:
        task.status = 'started'
        task.started_at = timezone.now()
        task.save()

        upload.status = VendorCSVUpload.STATUS_PROCESSING
        upload.save()

        # --- Setup Chroma client and embedding function ---
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name='sentence-transformers/all-MiniLM-L6-v2'
        )
        chroma_client = chromadb.Client()

        vendor_identifier = upload.vendor.id if upload.vendor else upload.vendor_id
        collection_name = _collection_name_for_vendor(vendor_identifier)

        # create collection if not exists
        existing = [c.name for c in chroma_client.list_collections()]
        if collection_name not in existing:
            collection = chroma_client.create_collection(
                name=collection_name,
                embedding_function=ef
            )
        else:
            collection = chroma_client.get_collection(name=collection_name, embedding_function=ef)

        # read CSV from uploaded file
        csv_path = upload.file.path
        df = pd.read_csv(csv_path)
        if 'question' not in df.columns or 'answer' not in df.columns:
            raise ValueError("CSV must contain 'question' and 'answer' columns")

        docs = df['question'].astype(str).tolist()
        metadatas = [{'answer': a} for a in df['answer'].astype(str).tolist()]
        ids = [f"{vendor_identifier}_upload{upload.id}_id_{i}" for i in range(len(docs))]

        # Option: if replacing existing collection entries is desired, you can delete and recreate
        # For now we append; implement atomic swap/versioning if needed.
        collection.add(documents=docs, metadatas=metadatas, ids=ids)

        upload.status = VendorCSVUpload.STATUS_COMPLETED
        upload.save()

        task.status = 'finished'
        task.finished_at = timezone.now()
        task.save()
    except Exception as exc:
        upload.status = VendorCSVUpload.STATUS_FAILED
        upload.error_message = str(exc)
        upload.save()

        task.status = 'failed'
        task.error_message = str(exc)
        task.finished_at = timezone.now()
        task.save()
        raise
