"""
Webhook handlers for Tenovi events.
"""
import json
import hmac
import hashlib
import logging
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from apps.core.models import get_collection
from apps.vitals.models import Vital
from apps.devices.models import Device
from apps.orders.services import OrderService

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Webhook event logging."""

    collection_name = 'webhook_events'

    @classmethod
    def log(cls, event_type: str, payload: dict, status: str = 'received'):
        """Log a webhook event."""
        collection = get_collection(cls.collection_name)
        document = {
            'event_type': event_type,
            'payload': payload,
            'status': status,
            'created_at': datetime.utcnow(),
        }
        return collection.insert_one(document)

    @classmethod
    def update_status(cls, event_id, status: str, error: str = None):
        """Update webhook event status."""
        collection = get_collection(cls.collection_name)
        update = {'status': status, 'processed_at': datetime.utcnow()}
        if error:
            update['error'] = error
        collection.update_one({'_id': event_id}, {'$set': update})


def verify_webhook_signature(request) -> bool:
    """
    Verify Tenovi webhook signature.
    In sandbox mode, always returns True.
    """
    if settings.TENOVI_SANDBOX_MODE:
        return True

    secret = settings.TENOVI_WEBHOOK_SECRET
    if not secret:
        logger.warning("TENOVI_WEBHOOK_SECRET not configured")
        return False

    signature = request.headers.get('X-Tenovi-Signature', '')
    if not signature:
        return False

    expected = hmac.new(
        secret.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


@csrf_exempt
@require_http_methods(['POST'])
def measurement_webhook(request):
    """
    Handle Tenovi measurement webhooks.

    Expected payload:
    {
        "event_type": "measurement",
        "device_id": "...",
        "patient_id": "...",
        "device_type": "blood_pressure",
        "timestamp": "2024-01-15T10:30:00Z",
        "readings": {
            "systolic": 120,
            "diastolic": 80,
            "pulse": 72
        },
        "metadata": {...}
    }
    """
    if not verify_webhook_signature(request):
        return JsonResponse({'error': 'Invalid signature'}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Log the event
    event = WebhookEvent.log('measurement', payload)

    try:
        # Parse timestamp
        timestamp = payload.get('timestamp')
        if timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()

        # Find device by hwi_device_id
        device = None
        hwi_device_id = payload.get('device_id')
        if hwi_device_id:
            device = Device.find_one({'hwi_device_id': hwi_device_id})

        # Create vital record
        vital_data = {
            'patient_id': payload.get('patient_id'),
            'device_id': str(device['_id']) if device else None,
            'device_type': payload.get('device_type'),
            'timestamp': timestamp,
            'readings': payload.get('readings', {}),
            'metadata': payload.get('metadata', {}),
            'source': 'tenovi_webhook',
        }

        Vital.create(vital_data)

        # Update device last reading
        if device:
            Device.record_reading(device['_id'], timestamp)

        WebhookEvent.update_status(event.inserted_id, 'processed')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.exception("Error processing measurement webhook")
        WebhookEvent.update_status(event.inserted_id, 'error', str(e))
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def fulfillment_webhook(request):
    """
    Handle Tenovi fulfillment webhooks.

    Expected payload:
    {
        "event_type": "fulfillment",
        "order_id": "...",
        "status": "shipped",
        "tracking_number": "...",
        "tracking_url": "...",
        "shipped_at": "2024-01-15T10:30:00Z",
        "items": [...]
    }
    """
    if not verify_webhook_signature(request):
        return JsonResponse({'error': 'Invalid signature'}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Log the event
    event = WebhookEvent.log('fulfillment', payload)

    try:
        order_service = OrderService()
        order_service.process_fulfillment_update(
            vendor_order_id=payload.get('order_id'),
            status=payload.get('status'),
            tracking_number=payload.get('tracking_number'),
            tracking_url=payload.get('tracking_url'),
        )

        WebhookEvent.update_status(event.inserted_id, 'processed')

        return JsonResponse({'status': 'ok'})

    except ValueError as e:
        logger.warning(f"Fulfillment webhook warning: {e}")
        WebhookEvent.update_status(event.inserted_id, 'warning', str(e))
        return JsonResponse({'status': 'ok', 'warning': str(e)})

    except Exception as e:
        logger.exception("Error processing fulfillment webhook")
        WebhookEvent.update_status(event.inserted_id, 'error', str(e))
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def device_registration_webhook(request):
    """
    Handle Tenovi device registration webhooks.

    Expected payload:
    {
        "event_type": "device_registration",
        "device_id": "...",
        "serial_number": "...",
        "device_type": "...",
        "patient_id": "...",
        "registered_at": "..."
    }
    """
    if not verify_webhook_signature(request):
        return JsonResponse({'error': 'Invalid signature'}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Log the event
    event = WebhookEvent.log('device_registration', payload)

    try:
        # Find device by serial number
        serial_number = payload.get('serial_number')
        device = Device.find_by_serial(serial_number)

        if device:
            # Update device with Tenovi device ID
            Device.update(device['_id'], {
                'hwi_device_id': payload.get('device_id'),
                'status': Device.STATUS_ACTIVE,
            })
        else:
            # Create new device record
            Device.create({
                'serial_number': serial_number,
                'hwi_device_id': payload.get('device_id'),
                'device_type': payload.get('device_type'),
                'patient_id': payload.get('patient_id'),
                'status': Device.STATUS_ACTIVE,
            })

        WebhookEvent.update_status(event.inserted_id, 'processed')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.exception("Error processing device registration webhook")
        WebhookEvent.update_status(event.inserted_id, 'error', str(e))
        return JsonResponse({'error': str(e)}, status=500)


def webhook_status(request):
    """View recent webhook events (for debugging)."""
    from django.shortcuts import render
    import json as json_module

    collection = get_collection('webhook_events')
    events = list(collection.find().sort('created_at', -1).limit(50))

    # Count by status
    processed_count = sum(1 for e in events if e.get('status') == 'processed')
    error_count = sum(1 for e in events if e.get('status') == 'error')

    # Serialize events
    for event in events:
        event['id'] = str(event.pop('_id'))
        # Keep datetime objects for template filters
        # Also create JSON version for payload modal
        event['payload_json'] = json_module.dumps(event.get('payload', {}))

    context = {
        'events': events,
        'total_events': len(events),
        'processed_count': processed_count,
        'error_count': error_count,
    }

    # Return JSON if requested via API
    if request.GET.get('format') == 'json':
        # Serialize for JSON response
        json_events = []
        for event in events:
            json_event = dict(event)
            if 'created_at' in json_event and json_event['created_at']:
                json_event['created_at'] = json_event['created_at'].isoformat()
            if 'processed_at' in json_event and json_event['processed_at']:
                json_event['processed_at'] = json_event['processed_at'].isoformat()
            json_events.append(json_event)
        return JsonResponse({'events': json_events})

    return render(request, 'webhooks/status.html', context)
