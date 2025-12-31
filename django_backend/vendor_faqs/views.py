from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Vendor, VendorCSVUpload, VendorIngestionTask
from .serializers import VendorCSVUploadSerializer, VendorIngestionTaskSerializer
from .tasks import ingest_vendor_csv_task
from .serializers import VendorSerializer
from rest_framework import generics
import pandas as pd
from pathlib import Path
import sys
import os
import tempfile

# Add parent directory to path so we can import Streamlit app code
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))


class CSVUploadView(APIView):
    """POST /api/vendors/{vendor_id}/csv-uploads/ - upload a CSV file for the vendor"""

    def post(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        if 'file' not in request.FILES:
            return Response({'detail': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)
        upload = VendorCSVUpload(vendor=vendor, file=request.FILES['file'])
        upload.save()
        serializer = VendorCSVUploadSerializer(upload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TriggerIngestView(APIView):
    """POST /api/vendors/{vendor_id}/faqs/ingest/ - trigger ingestion for vendor or upload"""

    def post(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        upload_id = request.data.get('upload_id')
        if upload_id:
            upload = get_object_or_404(VendorCSVUpload, pk=upload_id, vendor=vendor)
        else:
            # pick the most recent pending upload
            upload = vendor.uploads.order_by('-created_at').first()
            if not upload:
                return Response({'detail': 'no uploads found for vendor'}, status=status.HTTP_404_NOT_FOUND)

        task = VendorIngestionTask.objects.create(upload=upload, status='queued')
        # enqueue Celery task
        res = ingest_vendor_csv_task.delay(upload.id, task.id)
        task.celery_task_id = res.id
        task.save()
        serializer = VendorIngestionTaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class UploadStatusView(APIView):
    """GET /api/vendors/{vendor_id}/csv-uploads/{upload_id}/status/"""

    def get(self, request, vendor_id, upload_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        upload = get_object_or_404(VendorCSVUpload, pk=upload_id, vendor=vendor)
        serializer = VendorCSVUploadSerializer(upload)
        return Response(serializer.data)


class FAQListView(APIView):
    """GET /api/vendors/{vendor_id}/faqs/ - return raw CSV rows for the latest upload (simple fallback)
    Note: For production, prefer serving processed embeddings or a Chroma-backed API.
    """

    def get(self, request, vendor_id):
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        upload = vendor.uploads.order_by('-created_at').first()
        if not upload or not upload.file:
            return Response({'detail': 'no faq uploads'}, status=status.HTTP_404_NOT_FOUND)
        # read CSV and return rows
        import pandas as pd
        df = pd.read_csv(upload.file.path)
        rows = df.to_dict(orient='records')
        return Response({'upload_id': upload.id, 'rows': rows})


class VendorListCreateView(generics.ListCreateAPIView):
    """GET /api/vendors/ - list vendors
       POST /api/vendors/ {name, slug} - create a vendor
    """
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer


# ============ HTML Views (Web UI) ============

def home(request):
    """Home page"""
    return render(request, 'home.html', {
        'vendors_count': Vendor.objects.count(),
        'uploads_count': VendorCSVUpload.objects.count(),
    })


def vendor_list_view(request):
    """Vendor management UI"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        if name and slug:
            try:
                Vendor.objects.create(name=name, slug=slug)
                messages.success(request, f'Vendor "{name}" created successfully!')
                return redirect('vendor_list_view')
            except Exception as e:
                messages.error(request, f'Error creating vendor: {e}')
    
    vendors = Vendor.objects.all()
    return render(request, 'vendor_list.html', {'vendors': vendors})


def csv_upload_view(request):
    """CSV upload UI"""
    selected_vendor_id = request.GET.get('vendor_id') or request.POST.get('vendor_id')
    vendors = Vendor.objects.all()
    upload_result = None
    
    if request.method == 'POST':
        vendor_id = request.POST.get('vendor_id')
        csv_file = request.FILES.get('file')
        
        if not vendor_id or not csv_file:
            messages.error(request, 'Vendor and CSV file are required.')
        else:
            tmp_path = None
            try:
                vendor = Vendor.objects.get(pk=vendor_id)
                
                # Validate CSV columns
                tmp_path = None
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp:
                    tmp_path = tmp.name
                    for chunk in csv_file.chunks():
                        tmp.write(chunk)
                
                # Read and validate with pandas
                df = pd.read_csv(tmp_path)
                if 'question' not in df.columns or 'answer' not in df.columns:
                    messages.error(request, "CSV must contain 'question' and 'answer' columns.")
                    return render(request, 'csv_upload.html', {
                        'vendors': vendors,
                        'selected_vendor_id': int(vendor_id),
                    })
                
                # Create upload and trigger ingestion
                csv_file.seek(0)  # Reset file pointer
                upload = VendorCSVUpload.objects.create(
                    vendor=vendor,
                    file=csv_file,
                    filename=csv_file.name,
                )
                
                task = VendorIngestionTask.objects.create(upload=upload, status='queued')
                res = ingest_vendor_csv_task.delay(upload.id, task.id)
                task.celery_task_id = res.id
                task.save()
                
                upload_result = {
                    'success': True,
                    'upload_id': upload.id,
                    'filename': upload.filename,
                    'status': upload.status,
                    'vendor_id': vendor.id,
                }
                messages.success(request, f'CSV uploaded and ingestion queued!')
                selected_vendor_id = vendor_id
                
            except Exception as e:
                messages.error(request, f'Error uploading CSV: {e}')
                upload_result = {'success': False, 'error': str(e)}
            finally:
                # Clean up temp file
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass  # Ignore cleanup errors
    
    return render(request, 'csv_upload.html', {
        'vendors': vendors,
        'selected_vendor_id': int(selected_vendor_id) if selected_vendor_id else None,
        'upload_result': upload_result,
    })


def ingestion_status_view(request):
    """Ingestion status UI"""
    selected_vendor_id = request.GET.get('vendor_id')
    vendors = Vendor.objects.all()
    uploads = []
    selected_vendor = None
    
    if selected_vendor_id:
        selected_vendor = get_object_or_404(Vendor, pk=selected_vendor_id)
        uploads = selected_vendor.uploads.order_by('-created_at')
    
    return render(request, 'ingestion_status.html', {
        'vendors': vendors,
        'selected_vendor_id': int(selected_vendor_id) if selected_vendor_id else None,
        'selected_vendor': selected_vendor,
        'uploads': uploads,
    })


def chat_view(request):
    """FAQ chat UI with router-based response logic"""
    import json
    from .router import router
    from .faq import faq_chain
    from .llm_response import llm_chain
    

    selected_vendor_id = request.GET.get('vendor_id')
    vendors = Vendor.objects.all()
    selected_vendor = None
    chat_messages = []

    def ask(query, vendor_id):
        """Route query and get appropriate response"""
        route = router(query).name
        if route == 'faq':
            print('faq_route')
            return faq_chain(query, vendor_id)
        elif route == 'llm_response':
            print('llm_response_route')
            return llm_chain(query, vendor_id)
        else:
            return f"Route {route} not implemented yet"

    # Handle AJAX POST requests (JSON)
    if request.method == 'POST' and request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            vendor_id = data.get('vendor_id')
            query = data.get('query', '').strip()

            if not vendor_id or not query:
                return JsonResponse({'success': False, 'error': 'vendor_id and query required'}, status=400)

            try:
                response = ask(query, vendor_id)
                return JsonResponse({'success': True, 'response': response})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # Handle regular GET/POST requests (HTML)
    if selected_vendor_id:
        selected_vendor = get_object_or_404(Vendor, pk=selected_vendor_id)

        # Retrieve messages from session
        if 'chat_messages' not in request.session:
            request.session['chat_messages'] = []
        chat_messages = request.session['chat_messages']

        # Handle form POST
        if request.method == 'POST' and request.content_type != 'application/json':
            query = request.POST.get('query', '').strip()
            if query:
                chat_messages.append({'role': 'user', 'content': query})
                try:
                    response = ask(query, selected_vendor_id)
                    chat_messages.append({'role': 'assistant', 'content': response})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    chat_messages.append({'role': 'assistant', 'content': error_msg})

                request.session['chat_messages'] = chat_messages
                request.session.modified = True

    return render(request, 'chat.html', {
        'vendors': vendors,
        'selected_vendor_id': int(selected_vendor_id) if selected_vendor_id else None,
        'selected_vendor': selected_vendor,
        'messages': chat_messages,
    })