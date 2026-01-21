# CareAtlas Device Management Portal: Complete Build Specification

## Executive summary

This specification details a comprehensive device management portal for CareAtlas's HealthQuilt platform, integrating with Tenovi's drop-ship RPM device ecosystem. The portal will consolidate fragmented workflows—device ordering, ticket management, vitals monitoring, and operational reporting—into a unified Django + HTMX application serving internal ops teams and care navigators.

**Key architectural decisions**: MongoDB for flexible device/patient schemas with time-series vitals storage; Tenovi API integration via webhooks and REST for real-time order and vitals sync; HTMX + Alpine.js for dynamic, SPA-like UX without heavy JavaScript; and DaisyUI + Tailwind for rapid, healthcare-appropriate UI development.

---

## Part 1: Tenovi API integration architecture

### Authentication and base configuration

Tenovi uses **API Key authentication** via header: `Authorization: Api-Key {TENOVI_API_KEY}`. All requests require HTTPS to the client-specific endpoint: `https://api2.tenovi.com/clients/{CLIENT_DOMAIN}`.

**Critical constraints**: Rate limit of **1 request per second** per API key. The system isolates client data in separate databases for HIPAA compliance.

```python
# config/settings.py
TENOVI_API_KEY = env('TENOVI_API_KEY')
TENOVI_CLIENT_DOMAIN = env('TENOVI_CLIENT_DOMAIN')
TENOVI_BASE_URL = f"https://api2.tenovi.com/clients/{TENOVI_CLIENT_DOMAIN}"
TENOVI_WEBHOOK_SECRET = env('TENOVI_WEBHOOK_SECRET')  # For signature validation
```

### Core endpoint catalog

| Function | Endpoint | Methods | Purpose |
|----------|----------|---------|---------|
| **Device Activation** | `/hwi/hwi-devices/` | GET, POST | List/create activated devices |
| **Device Deactivation** | `/hwi/hwi-devices/{id}/` | DELETE | Remove device from system |
| **Device Types** | `/hwi/hwi-device-types/` | GET | Available devices with pricing |
| **Device Replacement** | `/hwi/hwi-devices/{id}/replacement/` | POST | Request replacement device/gateway |
| **Bulk Orders** | `/hwi/bulk-orders/` | GET, POST | High-volume ordering |
| **Patients** | `/hwi/hwi-patients/` | CRUD | Patient record management |
| **Measurements** | `/hwi/hwi-devices/{id}/measurements/` | GET | Device-specific vitals |
| **Patient Measurements** | `/hwi/patients/{patient_id}/measurements/` | GET | Aggregated patient vitals |
| **Gateways** | `/hwi/hwi-gateways/` | GET | Cellular gateway management |
| **Supplies** | `/asr/supply-requests/` | POST | Test strips, lancets ordering |

### Device activation flow patterns

Three activation scenarios drive the CareAtlas workflow:

**Scenario 1: Tenovi drop-ships directly (primary use case)**
```python
# Patient needs new device - Tenovi fulfills and ships
payload = {
    "device": {
        "name": "Blood Pressure Monitor",
        "hardware_uuid": None,  # No gateway ID yet
        "fulfillment_request": {
            "shipping_name": "John Doe",
            "shipping_address": "123 Main St",
            "shipping_city": "Springfield",
            "shipping_state": "IL",
            "shipping_zip_code": "62701",
            "client_will_fulfill": False,  # Tenovi ships
            "notify_emails": "carenavigator@careatlas.com",
            "require_signature": True  # For proof of delivery
        }
    },
    "patient_id": "CA-PAT-12345"  # CareAtlas patient identifier
}
```

**Scenario 2: Device replacement**
```python
# Existing device malfunctioning - request replacement
response = client.post(f"/hwi/hwi-devices/{hwi_device_id}/replacement/", {
    "replacement_reason": "device_malfunction",
    "replace_gateway": True,
    "replace_device": True
})
# Original HWI Device record maintained; hardware_uuid auto-updates
```

### Webhook integration layer

Tenovi delivers two critical webhook event streams:

**Measurement webhooks** fire when patients take readings:
```python
# webhooks/views.py
@csrf_exempt
@require_POST
def tenovi_measurement_webhook(request):
    """Handle incoming vitals data from Tenovi devices."""
    # Validate webhook signature
    if not verify_tenovi_signature(request):
        return HttpResponse(status=401)
    
    payload = json.loads(request.body)
    measurements = payload if isinstance(payload, list) else [payload]
    
    for measurement in measurements:
        # Store immediately, process async
        WebhookEvent.objects.create(
            event_type='measurement',
            payload=measurement,
            status='received'
        )
        process_measurement.delay(measurement)
    
    return HttpResponse(status=200)  # Must respond quickly
```

**Fulfillment webhooks** track order lifecycle:
| Status | Description |
|--------|-------------|
| `Dropship Requested` | Order submitted to Tenovi |
| `Ready to Ship` | Queued for fulfillment |
| `Shipped` | In transit with tracking |
| `Delivered` | Confirmed delivery |
| `Connected` | Device first synced data |
| `Client Action Required` | Address invalid or duplicate |
| `Returned` | Device returned to warehouse |
| `Replaced` | Replacement device shipped |

### Tenovi API client implementation

```python
# integrations/tenovi/client.py
import requests
from django.conf import settings
from functools import lru_cache
from time import sleep

class TenoviAPIClient:
    """Rate-limited client for Tenovi HWI API."""
    
    def __init__(self):
        self.base_url = settings.TENOVI_BASE_URL
        self.headers = {
            "Authorization": f"Api-Key {settings.TENOVI_API_KEY}",
            "Content-Type": "application/json"
        }
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Enforce 1 request/second rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 1:
            sleep(1 - elapsed)
        self._last_request_time = time.time()
    
    def create_device_order(self, patient_id: str, device_type: str, 
                           shipping_address: dict) -> dict:
        """Create new device order with drop-ship fulfillment."""
        self._rate_limit()
        payload = {
            "device": {
                "name": device_type,
                "hardware_uuid": None,
                "fulfillment_request": {
                    **shipping_address,
                    "client_will_fulfill": False,
                    "require_signature": True
                }
            },
            "patient_id": patient_id
        }
        response = requests.post(
            f"{self.base_url}/hwi/hwi-devices/",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_patient_measurements(self, patient_id: str, 
                                  metric: str = None,
                                  since: datetime = None) -> list:
        """Retrieve vitals readings for a patient."""
        self._rate_limit()
        params = {}
        if metric:
            params['metric__name'] = metric
        if since:
            params['created__gte'] = since.isoformat() + 'Z'
        
        response = requests.get(
            f"{self.base_url}/hwi/patients/{patient_id}/measurements/",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

# Singleton instance
tenovi_client = TenoviAPIClient()
```

### Supported device types

Tenovi offers **40+ device models** across categories:

| Category | Key Devices | Sensor Code | Metrics |
|----------|-------------|-------------|---------|
| **Blood Pressure** | Tenovi BPM, BPM-XL, Cellular BPM, OMRON Series | 10 | systolic, diastolic, pulse |
| **Glucose** | Tenovi BGM, Cellular BGM, Trividia | 12 | glucose (mg/dL), meal context |
| **Weight** | Tenovi Scale, Bariatric Scale, A&D Medical | 13 | weight (lbs) |
| **Pulse Oximetry** | Tenovi Pulse Ox, Nonin | 11 | SpO2 (%), pulse |
| **Other** | Peak Flow Meter, Thermometer, Smart Pillbox | varies | device-specific |

---

## Part 2: Data models and MongoDB schema design

### Collection architecture overview

The schema uses a **hybrid embedding strategy**: embed frequently co-accessed data (device assignments in patients, recent status history in devices) while referencing high-cardinality or independently-queried data (vitals time-series, full audit history).

```
Collections:
├── patients          # Core patient records with embedded device assignments
├── devices           # Device lifecycle with embedded recent history
├── orders            # Fulfillment tracking with embedded status transitions
├── vitals            # Time-series collection for readings
├── tickets           # Support tickets with embedded conversations
├── webhook_events    # Append-only event log with TTL
└── audit_logs        # HIPAA-compliant activity tracking
```

### Patients collection

```python
# apps/patients/models.py
from django_mongoengine import Document, EmbeddedDocument, fields

class Address(EmbeddedDocument):
    street = fields.StringField()
    city = fields.StringField()
    state = fields.StringField(max_length=2)
    zip_code = fields.StringField(max_length=10)

class DeviceAssignment(EmbeddedDocument):
    """Embedded current device assignments (typically 1-5 per patient)."""
    device_id = fields.ObjectIdField()
    hwi_device_id = fields.StringField()  # Tenovi's UUID
    device_type = fields.StringField(choices=[
        'blood_pressure_monitor', 'glucose_meter', 'scale', 
        'pulse_oximeter', 'thermometer', 'peak_flow_meter'
    ])
    serial_number = fields.StringField()
    assigned_at = fields.DateTimeField()
    status = fields.StringField(default='active')

class Patient(Document):
    """Patient record with PHI requiring encryption."""
    meta = {
        'collection': 'patients',
        'indexes': [
            {'fields': ['mrn'], 'unique': True},
            {'fields': ['external_id']},
            {'fields': ['last_name', 'first_name', 'date_of_birth']},
            {'fields': ['devices.device_id']},
            {'fields': ['care_navigator_id', 'is_active']},
        ]
    }
    
    # Identifiers
    mrn = fields.StringField(required=True, unique=True)
    external_id = fields.StringField()  # For Tenovi patient_id
    
    # PHI - encrypt at application layer
    first_name = fields.StringField(required=True)
    last_name = fields.StringField(required=True)
    date_of_birth = fields.DateTimeField(required=True)
    phone = fields.StringField()
    email = fields.StringField()
    
    # Address (PHI)
    shipping_address = fields.EmbeddedDocumentField(Address)
    
    # Program enrollment
    program = fields.StringField(choices=['RPM', 'CCM', 'TCM'])
    enrolled_at = fields.DateTimeField()
    care_navigator_id = fields.StringField()
    primary_conditions = fields.ListField(fields.StringField())
    
    # Embedded device assignments
    devices = fields.ListField(fields.EmbeddedDocumentField(DeviceAssignment))
    
    # Soft delete
    is_active = fields.BooleanField(default=True)
    deactivated_at = fields.DateTimeField()
    
    # Audit
    created_at = fields.DateTimeField()
    updated_at = fields.DateTimeField()
    created_by = fields.StringField()
    updated_by = fields.StringField()
```

### Devices collection

```python
# apps/devices/models.py
class StatusChange(EmbeddedDocument):
    """Embedded status history for quick access."""
    status = fields.StringField()
    timestamp = fields.DateTimeField()
    changed_by = fields.StringField()
    source = fields.StringField(choices=['webhook', 'manual', 'system'])
    notes = fields.StringField()
    tracking_number = fields.StringField()

class Device(Document):
    """Device lifecycle tracking with Tenovi integration."""
    meta = {
        'collection': 'devices',
        'indexes': [
            {'fields': ['serial_number'], 'unique': True},
            {'fields': ['hwi_device_id'], 'unique': True, 'sparse': True},
            {'fields': ['status', 'device_type']},
            {'fields': ['current_patient_id', 'status']},
            {'fields': ['order_id']},
        ]
    }
    
    STATUSES = [
        'ordered', 'dropship_requested', 'shipped', 'delivered',
        'assigned', 'active', 'inactive', 'returned', 
        'refurbishment', 'decommissioned'
    ]
    
    # Identifiers
    serial_number = fields.StringField(required=True, unique=True)
    hwi_device_id = fields.StringField()  # Tenovi's UUID
    hardware_uuid = fields.StringField()  # Gateway MAC address
    
    # Device info
    device_type = fields.StringField(required=True)
    manufacturer = fields.StringField(default='Tenovi')
    model = fields.StringField()
    sensor_code = fields.StringField(max_length=3)
    firmware_version = fields.StringField()
    
    # Current state
    status = fields.StringField(choices=STATUSES)
    current_patient_id = fields.ObjectIdField()
    order_id = fields.ObjectIdField()
    
    # Connectivity tracking
    last_reading_at = fields.DateTimeField()
    last_sync_at = fields.DateTimeField()
    connectivity_status = fields.StringField(choices=[
        'connected', 'intermittent', 'offline', 'never_connected'
    ])
    
    # Embedded recent history (last 20 transitions)
    status_history = fields.ListField(
        fields.EmbeddedDocumentField(StatusChange),
        max_length=20
    )
    
    # Alert thresholds (patient-specific overrides)
    alert_thresholds = fields.DictField()
    
    # Lifecycle
    is_deleted = fields.BooleanField(default=False)
    version = fields.IntField(default=1)
    created_at = fields.DateTimeField()
    updated_at = fields.DateTimeField()
    
    def update_status(self, new_status: str, user_id: str, 
                      source: str = 'manual', **kwargs):
        """Update device status with history tracking."""
        change = StatusChange(
            status=new_status,
            timestamp=datetime.utcnow(),
            changed_by=user_id,
            source=source,
            **kwargs
        )
        # Maintain max 20 history entries
        if len(self.status_history) >= 20:
            self.status_history.pop(0)
        self.status_history.append(change)
        self.status = new_status
        self.version += 1
        self.updated_at = datetime.utcnow()
        self.save()
```

### Orders collection

```python
# apps/orders/models.py
class OrderItem(EmbeddedDocument):
    device_type = fields.StringField(required=True)
    quantity = fields.IntField(default=1)
    sku = fields.StringField()
    serial_numbers = fields.ListField(fields.StringField())  # Populated post-fulfillment

class OrderStatusChange(EmbeddedDocument):
    status = fields.StringField()
    timestamp = fields.DateTimeField()
    source = fields.StringField(choices=['webhook', 'manual', 'system'])
    details = fields.StringField()

class Order(Document):
    """Device order with Tenovi drop-ship fulfillment tracking."""
    meta = {
        'collection': 'orders',
        'indexes': [
            {'fields': ['order_number'], 'unique': True},
            {'fields': ['vendor_order_id']},
            {'fields': ['patient_id', '-created_at']},
            {'fields': ['status', 'estimated_delivery']},
            {'fields': ['care_navigator_id', 'status']},
        ]
    }
    
    STATUSES = [
        'pending', 'dropship_requested', 'ready_to_ship', 'shipped',
        'delivered', 'cancelled', 'client_action_required', 'on_hold'
    ]
    ORDER_TYPES = ['device_shipment', 'replacement', 'supplies', 'return_label']
    
    # Identifiers
    order_number = fields.StringField(required=True)  # CA-ORD-YYYYMMDD-XXXX
    vendor_order_id = fields.StringField()  # Tenovi reference
    
    # Order details
    order_type = fields.StringField(choices=ORDER_TYPES)
    items = fields.ListField(fields.EmbeddedDocumentField(OrderItem))
    
    # Shipping
    shipping_address = fields.EmbeddedDocumentField(Address)
    shipping_method = fields.StringField(default='ground')
    carrier = fields.StringField()
    tracking_number = fields.StringField()
    tracking_url = fields.StringField()
    require_signature = fields.BooleanField(default=True)
    
    # Status
    status = fields.StringField(choices=STATUSES)
    status_history = fields.ListField(fields.EmbeddedDocumentField(OrderStatusChange))
    estimated_delivery = fields.DateTimeField()
    actual_delivery = fields.DateTimeField()
    
    # References
    patient_id = fields.ObjectIdField(required=True)
    care_navigator_id = fields.StringField()
    
    # Notes
    special_instructions = fields.StringField()
    internal_notes = fields.StringField()
    
    # Audit
    created_by = fields.StringField()
    created_at = fields.DateTimeField()
    updated_at = fields.DateTimeField()
```

### Vitals time-series collection

MongoDB's native time-series collections provide **80% storage reduction** and optimized time-range queries:

```javascript
// MongoDB shell - create time-series collection
db.createCollection("vitals", {
  timeseries: {
    timeField: "timestamp",
    metaField: "metadata",
    granularity: "minutes"
  },
  expireAfterSeconds: 220752000  // 7 years (HIPAA requirement)
})
```

```python
# apps/vitals/models.py
from pymongo import MongoClient

class VitalsManager:
    """Manager for time-series vitals data using raw PyMongo."""
    
    METRICS_SCHEMA = {
        'blood_pressure': {
            'value_1': 'systolic_mmhg',
            'value_2': 'diastolic_mmhg',
            'additional': ['pulse']
        },
        'weight': {
            'value_1': 'weight_lbs',
            'value_2': None
        },
        'glucose': {
            'value_1': 'glucose_mg_dl',
            'value_2': None,
            'additional': ['meal_context']
        },
        'spO2': {
            'value_1': 'oxygen_saturation_pct',
            'value_2': None,
            'additional': ['pulse']
        }
    }
    
    def __init__(self, db):
        self.collection = db['vitals']
    
    def record_measurement(self, webhook_payload: dict):
        """Transform Tenovi webhook into vitals document."""
        doc = {
            "timestamp": datetime.fromisoformat(
                webhook_payload['created'].replace('Z', '+00:00')
            ),
            "metadata": {
                "patient_id": webhook_payload.get('patient_id'),
                "device_id": webhook_payload['hwi_device_id'],
                "device_type": webhook_payload['device_name'],
                "sensor_code": webhook_payload['sensor_code']
            },
            "readings": self._transform_readings(webhook_payload),
            "source": "tenovi_webhook",
            "raw_payload": webhook_payload
        }
        return self.collection.insert_one(doc)
    
    def get_patient_vitals(self, patient_id: str, 
                           metric: str = None,
                           start_date: datetime = None,
                           end_date: datetime = None,
                           limit: int = 100) -> list:
        """Query vitals with time-series optimization."""
        query = {"metadata.patient_id": patient_id}
        
        if metric:
            query["readings." + metric] = {"$exists": True}
        
        time_filter = {}
        if start_date:
            time_filter["$gte"] = start_date
        if end_date:
            time_filter["$lte"] = end_date
        if time_filter:
            query["timestamp"] = time_filter
        
        return list(self.collection.find(query)
                    .sort("timestamp", -1)
                    .limit(limit))
```

### Support tickets collection

```python
# apps/tickets/models.py
class TicketMessage(EmbeddedDocument):
    """Embedded conversation thread."""
    message_id = fields.ObjectIdField()
    type = fields.StringField(choices=['customer', 'agent', 'system', 'note'])
    content = fields.StringField()
    author_id = fields.StringField()
    author_name = fields.StringField()
    timestamp = fields.DateTimeField()
    attachments = fields.ListField(fields.DictField())

class Ticket(Document):
    """HIPAA-compliant support ticket."""
    meta = {
        'collection': 'tickets',
        'indexes': [
            {'fields': ['ticket_number'], 'unique': True},
            {'fields': ['patient_id', 'status']},
            {'fields': ['assigned_to', 'status', '-priority_score']},
            {'fields': ['device_id']},
            {'fields': ['status', '-updated_at']},
            {'fields': [
                ('subject', 'text'), 
                ('description', 'text')
            ], 'weights': {'subject': 10, 'description': 5}},
        ]
    }
    
    CATEGORIES = [
        'device_not_syncing', 'device_malfunction', 'shipping_issue',
        'order_change', 'patient_training', 'account_access',
        'clinical_escalation', 'billing', 'other'
    ]
    PRIORITIES = ['low', 'medium', 'high', 'urgent']
    STATUSES = ['open', 'in_progress', 'pending_patient', 
                'pending_vendor', 'resolved', 'closed']
    
    # Identifiers
    ticket_number = fields.StringField(required=True)  # TKT-YYYYMMDD-XXXX
    
    # Content
    subject = fields.StringField(required=True)
    description = fields.StringField()
    category = fields.StringField(choices=CATEGORIES)
    priority = fields.StringField(choices=PRIORITIES)
    priority_score = fields.IntField()  # For sorting: urgent=4, high=3, etc.
    status = fields.StringField(choices=STATUSES, default='open')
    
    # References (PHI links - access controlled)
    patient_id = fields.ObjectIdField()
    device_id = fields.ObjectIdField()
    order_id = fields.ObjectIdField()
    
    # Assignment
    assigned_to = fields.StringField()
    team = fields.StringField(choices=['device_support', 'logistics', 'clinical'])
    
    # Conversation thread (embedded)
    messages = fields.ListField(fields.EmbeddedDocumentField(TicketMessage))
    
    # Resolution
    resolution_category = fields.StringField()
    resolution_notes = fields.StringField()
    
    # SLA tracking
    first_response_at = fields.DateTimeField()
    sla_deadline = fields.DateTimeField()
    sla_breached = fields.BooleanField(default=False)
    
    # Time tracking (for billing/CPT codes)
    time_spent_minutes = fields.IntField(default=0)
    
    # Lifecycle
    created_at = fields.DateTimeField()
    updated_at = fields.DateTimeField()
    resolved_at = fields.DateTimeField()
    closed_at = fields.DateTimeField()
    created_by = fields.StringField()
```

---

## Part 3: View and template structure for HTMX

### URL configuration

```python
# config/urls.py
from django.urls import path, include

urlpatterns = [
    path('', include('apps.dashboard.urls')),
    path('patients/', include('apps.patients.urls')),
    path('devices/', include('apps.devices.urls')),
    path('orders/', include('apps.orders.urls')),
    path('tickets/', include('apps.tickets.urls')),
    path('vitals/', include('apps.vitals.urls')),
    path('reports/', include('apps.reports.urls')),
    path('webhooks/', include('apps.webhooks.urls')),
]

# apps/orders/urls.py
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # List views
    path('', views.OrderListView.as_view(), name='list'),
    path('create/', views.OrderCreateView.as_view(), name='create'),
    path('<str:order_id>/', views.OrderDetailView.as_view(), name='detail'),
    
    # HTMX partials
    path('htmx/table/', views.order_table_partial, name='htmx-table'),
    path('htmx/row/<str:order_id>/', views.order_row_partial, name='htmx-row'),
    path('htmx/status/<str:order_id>/', views.order_status_partial, name='htmx-status'),
    path('htmx/create-form/', views.order_create_form, name='htmx-create-form'),
    
    # Actions
    path('<str:order_id>/cancel/', views.order_cancel, name='cancel'),
    path('<str:order_id>/resubmit/', views.order_resubmit, name='resubmit'),
]
```

### HTMX view patterns

```python
# apps/orders/views.py
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django_htmx.http import HttpResponseClientRefresh
from django_tables2 import SingleTableMixin
from django_filter.views import FilterView

class OrderListView(SingleTableMixin, FilterView):
    """Main order list with filtering and HTMX support."""
    model = Order
    table_class = OrderTable
    filterset_class = OrderFilter
    template_name = 'orders/order_list.html'
    paginate_by = 25
    
    def get_template_names(self):
        if self.request.htmx:
            return ['orders/partials/order_table.html']
        return [self.template_name]

def order_create_form(request):
    """HTMX: Render order creation form in modal."""
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = create_device_order(form.cleaned_data, request.user)
            response = render(request, 'orders/partials/order_row.html', 
                            {'order': order})
            response['HX-Trigger'] = json.dumps({
                'showToast': {
                    'message': f'Order {order.order_number} created successfully',
                    'type': 'success'
                },
                'closeModal': True
            })
            return response
        return render(request, 'orders/partials/order_form.html', 
                     {'form': form}, status=422)
    
    # Pre-populate patient if provided
    patient_id = request.GET.get('patient_id')
    form = OrderCreateForm(initial={'patient_id': patient_id})
    return render(request, 'orders/partials/order_form.html', {'form': form})

def order_status_partial(request, order_id):
    """HTMX: Update order status display."""
    order = Order.objects.get(id=order_id)
    return render(request, 'orders/partials/order_status_badge.html', 
                 {'order': order})
```

### Template structure

```
templates/
├── base.html                    # Main layout with sidebar, navbar
├── components/
│   ├── toast.html              # Alpine.js toast notifications
│   ├── modal.html              # Generic modal container
│   ├── confirm_dialog.html     # Confirmation modal
│   ├── loading_spinner.html    # HTMX indicator
│   └── pagination.html         # HTMX-enabled pagination
├── orders/
│   ├── order_list.html         # Full page: order management
│   ├── order_detail.html       # Full page: order details
│   └── partials/
│       ├── order_table.html    # HTMX: table with rows
│       ├── order_row.html      # HTMX: single row for swap
│       ├── order_form.html     # HTMX: create/edit form
│       ├── order_filters.html  # HTMX: filter controls
│       └── order_status_badge.html
├── patients/
│   └── partials/
│       ├── patient_card.html
│       ├── device_assignment.html
│       └── vitals_chart.html
├── tickets/
│   └── partials/
│       ├── ticket_list.html
│       ├── ticket_detail.html
│       ├── message_thread.html
│       └── reply_form.html
└── dashboard/
    └── partials/
        ├── stats_cards.html
        ├── recent_orders.html
        ├── pending_tickets.html
        └── connectivity_alerts.html
```

### Base template with Alpine.js + HTMX

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}HealthQuilt{% endblock %}</title>
    
    <!-- Tailwind + DaisyUI -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet">
    
    <!-- Alpine.js + HTMX -->
    <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
    <script src="https://unpkg.com/htmx.org@2.0.0/dist/ext/alpine-morph.js"></script>
    
    <!-- Chart.js for vitals -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="min-h-screen bg-base-200" 
      hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'
      x-data="{ 
          toasts: [],
          showToast(message, type='success') {
              const id = Date.now();
              this.toasts.push({id, message, type});
              setTimeout(() => this.toasts = this.toasts.filter(t => t.id !== id), 4000);
          }
      }"
      @show-toast.window="showToast($event.detail.message, $event.detail.type)">

    <div class="drawer lg:drawer-open">
        <input id="drawer" type="checkbox" class="drawer-toggle">
        
        <!-- Main Content -->
        <div class="drawer-content flex flex-col">
            {% include 'components/navbar.html' %}
            
            <main id="main-content" class="p-6">
                {% block content %}{% endblock %}
            </main>
        </div>
        
        <!-- Sidebar -->
        <div class="drawer-side">
            <label for="drawer" class="drawer-overlay"></label>
            {% include 'components/sidebar.html' %}
        </div>
    </div>
    
    <!-- Toast Notifications -->
    <div class="toast toast-end">
        <template x-for="toast in toasts" :key="toast.id">
            <div class="alert" 
                 :class="{'alert-success': toast.type === 'success', 
                         'alert-error': toast.type === 'error',
                         'alert-warning': toast.type === 'warning'}">
                <span x-text="toast.message"></span>
            </div>
        </template>
    </div>
    
    <!-- Modal Container -->
    <div id="modal-container"></div>
</body>
</html>
```

### Order creation workflow template

```html
<!-- templates/orders/partials/order_form.html -->
<div class="modal-box max-w-2xl" x-data="{ step: 1, selectedPatient: null }">
    <h3 class="font-bold text-lg mb-4">Create Device Order</h3>
    
    <form hx-post="{% url 'orders:htmx-create-form' %}"
          hx-target="#order-table tbody"
          hx-swap="afterbegin"
          @htmx:after-request="if(event.detail.successful) $dispatch('close-modal')">
        {% csrf_token %}
        
        <!-- Step 1: Patient Selection -->
        <div x-show="step === 1" class="space-y-4">
            <div class="form-control">
                <label class="label">Search Patient</label>
                <input type="text" 
                       name="patient_search"
                       class="input input-bordered"
                       placeholder="Search by name or MRN..."
                       hx-get="{% url 'patients:htmx-search' %}"
                       hx-trigger="keyup changed delay:300ms"
                       hx-target="#patient-results">
            </div>
            <div id="patient-results" class="space-y-2"></div>
            
            <input type="hidden" name="patient_id" x-model="selectedPatient">
            
            <div class="flex justify-end">
                <button type="button" 
                        class="btn btn-primary"
                        :disabled="!selectedPatient"
                        @click="step = 2">
                    Next: Select Devices
                </button>
            </div>
        </div>
        
        <!-- Step 2: Device Selection -->
        <div x-show="step === 2" class="space-y-4">
            <div class="form-control">
                <label class="label">Select Devices</label>
                <div class="grid grid-cols-2 gap-4">
                    {% for device_type in device_types %}
                    <label class="cursor-pointer flex items-center gap-3 p-4 border rounded-lg hover:bg-base-200">
                        <input type="checkbox" 
                               name="device_types" 
                               value="{{ device_type.code }}"
                               class="checkbox checkbox-primary">
                        <div>
                            <div class="font-medium">{{ device_type.name }}</div>
                            <div class="text-sm text-gray-500">{{ device_type.description }}</div>
                        </div>
                    </label>
                    {% endfor %}
                </div>
            </div>
            
            <div class="flex justify-between">
                <button type="button" class="btn" @click="step = 1">Back</button>
                <button type="button" class="btn btn-primary" @click="step = 3">
                    Next: Shipping
                </button>
            </div>
        </div>
        
        <!-- Step 3: Shipping Confirmation -->
        <div x-show="step === 3" class="space-y-4">
            <div class="bg-base-200 p-4 rounded-lg">
                <h4 class="font-medium mb-2">Shipping Address</h4>
                <div id="shipping-address" 
                     hx-get="{% url 'patients:htmx-address' %}"
                     hx-trigger="load"
                     hx-vals='{"patient_id": selectedPatient}'>
                    Loading...
                </div>
            </div>
            
            <div class="form-control">
                <label class="label cursor-pointer">
                    <span>Require Signature</span>
                    <input type="checkbox" name="require_signature" 
                           checked class="checkbox checkbox-primary">
                </label>
            </div>
            
            <div class="form-control">
                <label class="label">Special Instructions</label>
                <textarea name="special_instructions" 
                          class="textarea textarea-bordered" 
                          rows="2"></textarea>
            </div>
            
            <div class="flex justify-between">
                <button type="button" class="btn" @click="step = 2">Back</button>
                <button type="submit" class="btn btn-primary">
                    <span class="htmx-indicator loading loading-spinner"></span>
                    Create Order
                </button>
            </div>
        </div>
    </form>
</div>
```

---

## Part 4: Care navigator workflows

### Workflow 1: Creating device orders for patients

**User story**: Care navigator identifies a patient needing RPM devices and creates an order that Tenovi fulfills via drop-ship.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Device Order Creation Flow                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ 1. Search    │───▶│ 2. Select    │───▶│ 3. Confirm   │          │
│  │    Patient   │    │    Devices   │    │    Shipping  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                   │                    │
│         ▼                   ▼                   ▼                    │
│  [MRN/Name search]  [BP, Glucose, Scale]  [Address verified]        │
│  [Recent patients]  [Device availability] [Special instructions]     │
│                                                   │                  │
│                                                   ▼                  │
│                              ┌──────────────────────────────┐       │
│                              │  4. Submit to Tenovi API     │       │
│                              │  POST /hwi/hwi-devices/      │       │
│                              └──────────────────────────────┘       │
│                                          │                          │
│                                          ▼                          │
│                              ┌──────────────────────────────┐       │
│                              │  5. Order Created            │       │
│                              │  Status: dropship_requested  │       │
│                              │  hwi_device_id returned      │       │
│                              └──────────────────────────────┘       │
│                                          │                          │
│                                          ▼                          │
│                              ┌──────────────────────────────┐       │
│                              │  6. Webhook Updates          │       │
│                              │  shipped → tracking added    │       │
│                              │  delivered → status updated  │       │
│                              │  connected → device active   │       │
│                              └──────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### Workflow 2: Tracking orders and shipping

**Dashboard components for order visibility**:

```python
# apps/orders/services.py
class OrderTrackingService:
    """Real-time order status aggregation."""
    
    def get_order_dashboard_stats(self, care_navigator_id: str = None):
        """Get order statistics for dashboard cards."""
        base_query = {}
        if care_navigator_id:
            base_query['care_navigator_id'] = care_navigator_id
        
        pipeline = [
            {"$match": base_query},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        results = Order.objects.aggregate(pipeline)
        return {r['_id']: r['count'] for r in results}
    
    def get_orders_requiring_attention(self):
        """Orders with issues needing care navigator action."""
        return Order.objects.filter(
            status__in=['client_action_required', 'on_hold'],
            created_at__gte=datetime.utcnow() - timedelta(days=30)
        ).order_by('-created_at')
    
    def get_stale_orders(self, days_threshold: int = 7):
        """Orders stuck in shipping status too long."""
        cutoff = datetime.utcnow() - timedelta(days=days_threshold)
        return Order.objects.filter(
            status='shipped',
            updated_at__lte=cutoff
        ).order_by('updated_at')
```

### Workflow 3: Managing device assignments

**Post-delivery device activation**:

```python
# apps/devices/services.py
class DeviceAssignmentService:
    """Handle device-to-patient relationships."""
    
    def activate_device_for_patient(self, device_id: str, 
                                    patient_id: str, 
                                    user_id: str):
        """Assign delivered device to patient."""
        device = Device.objects.get(id=device_id)
        patient = Patient.objects.get(id=patient_id)
        
        # Update device
        device.current_patient_id = patient.id
        device.update_status('assigned', user_id, source='manual')
        
        # Add to patient's device list
        assignment = DeviceAssignment(
            device_id=device.id,
            hwi_device_id=device.hwi_device_id,
            device_type=device.device_type,
            serial_number=device.serial_number,
            assigned_at=datetime.utcnow(),
            status='active'
        )
        patient.devices.append(assignment)
        patient.save()
        
        # Create audit log
        AuditLog.create_entry(
            user_id=user_id,
            action='device_assignment',
            model='Device',
            object_id=str(device.id),
            details={'patient_id': str(patient_id)}
        )
        
        return device, patient
    
    def get_connectivity_issues(self):
        """Devices not reporting data within expected timeframe."""
        cutoff = datetime.utcnow() - timedelta(days=3)
        return Device.objects.filter(
            status='active',
            last_reading_at__lte=cutoff
        ).select_related('current_patient')
```

### Workflow 4: Handling device issues and tickets

**Ticket creation from device alert**:

```python
# apps/tickets/services.py
class TicketService:
    """Support ticket management."""
    
    PRIORITY_SCORES = {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
    
    def create_ticket_from_alert(self, alert_type: str, 
                                  device_id: str,
                                  auto_assign: bool = True):
        """Auto-generate ticket from system alert."""
        device = Device.objects.get(id=device_id)
        patient = Patient.objects.get(id=device.current_patient_id)
        
        # Determine category and priority
        category, priority = self._classify_alert(alert_type)
        
        ticket = Ticket(
            ticket_number=self._generate_ticket_number(),
            subject=f"{alert_type}: {device.device_type} - {patient.last_name}",
            description=f"Automated ticket created for {alert_type}",
            category=category,
            priority=priority,
            priority_score=self.PRIORITY_SCORES[priority],
            status='open',
            patient_id=patient.id,
            device_id=device.id,
            team='device_support',
            created_by='system',
            created_at=datetime.utcnow()
        )
        
        if auto_assign:
            ticket.assigned_to = self._get_available_agent('device_support')
        
        ticket.save()
        return ticket
    
    def _classify_alert(self, alert_type: str):
        """Map alert types to ticket categories and priorities."""
        mappings = {
            'device_offline_3_days': ('device_not_syncing', 'medium'),
            'device_offline_7_days': ('device_not_syncing', 'high'),
            'critical_reading': ('clinical_escalation', 'urgent'),
            'delivery_failed': ('shipping_issue', 'high'),
        }
        return mappings.get(alert_type, ('other', 'medium'))
```

### Workflow 5: Viewing vitals data

**Vitals dashboard with Chart.js integration**:

```html
<!-- templates/patients/partials/vitals_chart.html -->
<div class="card bg-base-100 shadow-xl">
    <div class="card-body">
        <div class="flex justify-between items-center mb-4">
            <h3 class="card-title">Blood Pressure Trends</h3>
            <select class="select select-bordered select-sm"
                    hx-get="{% url 'vitals:htmx-chart-data' patient.id %}"
                    hx-target="#bp-chart-data"
                    hx-swap="innerHTML"
                    name="range">
                <option value="7">Last 7 days</option>
                <option value="30" selected>Last 30 days</option>
                <option value="90">Last 90 days</option>
            </select>
        </div>
        
        <div id="bp-chart-data"
             hx-get="{% url 'vitals:htmx-chart-data' patient.id %}?range=30"
             hx-trigger="load"
             hx-swap="innerHTML">
            <div class="animate-pulse h-64 bg-base-200 rounded"></div>
        </div>
    </div>
</div>

<!-- Returned by HTMX endpoint -->
<script>
    const ctx = document.getElementById('bp-chart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: {{ chart_labels|safe }},
            datasets: [{
                label: 'Systolic',
                data: {{ systolic_values|safe }},
                borderColor: 'rgb(239, 68, 68)',
                tension: 0.1
            }, {
                label: 'Diastolic',
                data: {{ diastolic_values|safe }},
                borderColor: 'rgb(59, 130, 246)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                annotation: {
                    annotations: {
                        highLine: {
                            type: 'line',
                            yMin: 140,
                            yMax: 140,
                            borderColor: 'rgba(239, 68, 68, 0.5)',
                            borderDash: [5, 5]
                        }
                    }
                }
            }
        }
    });
</script>
```

### Workflow 6: Running operational reports

**Report types for care navigators**:

| Report | Purpose | Key Metrics |
|--------|---------|-------------|
| **Reading Compliance** | Track patient engagement | % patients with daily readings, average readings/week |
| **Device Connectivity** | Identify non-reporting devices | Devices offline > 3 days, never-connected devices |
| **Order Pipeline** | Fulfillment tracking | Orders by status, average delivery time, stuck orders |
| **Ticket Aging** | SLA compliance | Open tickets by age, resolution time by category |
| **CPT Time Tracking** | Billing documentation | Minutes per patient, ready-to-bill patients |

```python
# apps/reports/views.py
class ComplianceReportView(View):
    """Patient reading compliance report."""
    
    def get(self, request):
        date_range = request.GET.get('range', 30)
        start_date = datetime.utcnow() - timedelta(days=int(date_range))
        
        # Aggregate readings per patient
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {"$group": {
                "_id": "$metadata.patient_id",
                "reading_count": {"$sum": 1},
                "unique_days": {"$addToSet": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                }},
                "last_reading": {"$max": "$timestamp"}
            }},
            {"$addFields": {
                "days_with_readings": {"$size": "$unique_days"},
                "compliance_rate": {
                    "$multiply": [
                        {"$divide": [{"$size": "$unique_days"}, date_range]},
                        100
                    ]
                }
            }},
            {"$sort": {"compliance_rate": 1}}  # Lowest compliance first
        ]
        
        results = list(vitals_collection.aggregate(pipeline))
        
        # Enrich with patient details
        patient_ids = [r['_id'] for r in results]
        patients = {str(p.id): p for p in Patient.objects.filter(
            id__in=patient_ids
        )}
        
        for r in results:
            r['patient'] = patients.get(r['_id'])
        
        return render(request, 'reports/compliance_report.html', {
            'results': results,
            'date_range': date_range,
            'summary': self._calculate_summary(results)
        })
```

---

## Part 5: Priority-ordered implementation phases

### Phase 1: Foundation (Weeks 1-3)

**Objective**: Core infrastructure, Tenovi integration, basic order flow

| Component | Priority | Effort | Description |
|-----------|----------|--------|-------------|
| Project setup | P0 | 2d | Django project, MongoDB, Tailwind, HTMX config |
| Tenovi API client | P0 | 3d | Rate-limited client, authentication, error handling |
| Webhook handlers | P0 | 3d | Measurement + fulfillment webhooks, signature validation |
| Patient model | P0 | 2d | Core patient CRUD with PHI encryption patterns |
| Device model | P0 | 2d | Device lifecycle, status transitions |
| Order model | P0 | 2d | Order creation, status tracking |
| Base templates | P0 | 2d | Layout, navigation, DaisyUI components |
| Order creation view | P0 | 3d | Multi-step form with HTMX |

**Deliverables**:
- Care navigators can create device orders
- Orders sync to Tenovi and receive webhook updates
- Basic patient and device management

### Phase 2: Device management (Weeks 4-5)

**Objective**: Complete device lifecycle, assignment, connectivity monitoring

| Component | Priority | Effort | Description |
|-----------|----------|--------|-------------|
| Device assignment | P1 | 2d | Link devices to patients post-delivery |
| Device detail view | P1 | 2d | Full device info, status history, readings |
| Connectivity monitoring | P1 | 3d | Detect offline devices, alert generation |
| Device replacement flow | P1 | 2d | Initiate replacements via Tenovi API |
| Order tracking dashboard | P1 | 2d | Status overview, attention-needed list |
| Audit logging | P1 | 2d | HIPAA-compliant activity tracking |

### Phase 3: Vitals and patient views (Weeks 6-7)

**Objective**: Vitals display, patient-centric views, basic alerting

| Component | Priority | Effort | Description |
|-----------|----------|--------|-------------|
| Vitals time-series | P1 | 3d | MongoDB time-series collection, ingestion |
| Vitals display | P1 | 3d | Chart.js visualizations, date filtering |
| Patient detail view | P1 | 3d | Unified patient view with devices, vitals, tickets |
| Clinical alerts | P2 | 3d | Threshold-based alerts, alert dashboard |
| Patient search | P1 | 2d | Full-text search, filter by program/navigator |

### Phase 4: Ticketing system (Weeks 8-9)

**Objective**: Complete support ticket workflow

| Component | Priority | Effort | Description |
|-----------|----------|--------|-------------|
| Ticket model | P1 | 2d | HIPAA-compliant fields, message threading |
| Ticket list/detail | P1 | 3d | Filterable list, full conversation view |
| Ticket creation | P1 | 2d | Manual + auto-generated from alerts |
| Assignment routing | P2 | 2d | Team-based assignment, workload balancing |
| SLA tracking | P2 | 2d | Deadline calculation, breach alerts |
| Time tracking | P2 | 2d | Per-ticket time logging for CPT codes |

### Phase 5: Reporting and polish (Weeks 10-12)

**Objective**: Operational reports, dashboard, performance optimization

| Component | Priority | Effort | Description |
|-----------|----------|--------|-------------|
| Dashboard home | P1 | 3d | Stats cards, recent activity, alerts |
| Compliance report | P2 | 2d | Patient reading engagement |
| Ticket analytics | P2 | 2d | Volume, resolution time, categories |
| Order pipeline report | P2 | 2d | Fulfillment metrics |
| CPT billing export | P2 | 2d | Time summaries for billing |
| Performance optimization | P2 | 3d | Query optimization, caching |
| User roles/permissions | P1 | 3d | RBAC for care navigators, admins |

---

## Part 6: Recommended third-party libraries

### Core stack

```python
# requirements.txt

# Django + Extensions
Django==5.1.4
django-htmx==1.17.3
django-render-block==0.10
django-template-partials==24.3

# MongoDB
django-mongodb-backend==5.0.0
pymongo==4.6.1

# Tables + Filtering
django-tables2==2.7.0
django-filter==24.1

# Forms
django-crispy-forms==2.1
crispy-tailwind==1.0.1

# Background Tasks
celery==5.4.0
django-celery-beat==2.6.0
redis==5.0.1

# API Client
requests==2.31.0
tenacity==8.2.3  # Retry logic

# Security
django-csp==3.8
django-permissions-policy==4.18.0
python-dotenv==1.0.0
cryptography==41.0.7  # PHI encryption

# Monitoring
sentry-sdk==1.38.0
django-silk==5.1.0  # Dev profiling

# Testing
pytest-django==4.7.0
factory-boy==3.3.0
```

### Frontend (via CDN or npm)

```json
{
  "dependencies": {
    "htmx.org": "^2.0.0",
    "alpinejs": "^3.13.0",
    "chart.js": "^4.4.0",
    "chartjs-plugin-annotation": "^3.0.1",
    "tailwindcss": "^3.4.0",
    "daisyui": "^4.4.0"
  }
}
```

---

## Part 7: Security and compliance architecture

### HIPAA technical safeguards

```python
# config/settings.py

# Session security
SESSION_COOKIE_AGE = 900  # 15-minute timeout
SESSION_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = True

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "cdn.tailwindcss.com", "unpkg.com", "cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net")

# PHI Encryption (application-layer)
PHI_ENCRYPTION_KEY = env('PHI_ENCRYPTION_KEY')

# Audit logging
AUDIT_LOG_RETENTION_DAYS = 2555  # 7 years
```

### Field-level encryption pattern

```python
# apps/core/encryption.py
from cryptography.fernet import Fernet
from django.conf import settings

class PHIEncryptor:
    """Encrypt/decrypt PHI fields at application layer."""
    
    def __init__(self):
        self.fernet = Fernet(settings.PHI_ENCRYPTION_KEY)
    
    def encrypt(self, value: str) -> str:
        if not value:
            return value
        return self.fernet.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted_value: str) -> str:
        if not encrypted_value:
            return encrypted_value
        return self.fernet.decrypt(encrypted_value.encode()).decode()

# Usage in models
class Patient(Document):
    _first_name_encrypted = fields.StringField()
    
    @property
    def first_name(self):
        return phi_encryptor.decrypt(self._first_name_encrypted)
    
    @first_name.setter
    def first_name(self, value):
        self._first_name_encrypted = phi_encryptor.encrypt(value)
```

### Role-based access control

```python
# apps/core/permissions.py
from django.contrib.auth.mixins import UserPassesTestMixin

class RoleRequiredMixin(UserPassesTestMixin):
    required_roles = []
    
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        return self.request.user.role in self.required_roles

class CareNavigatorRequired(RoleRequiredMixin):
    required_roles = ['care_navigator', 'supervisor', 'admin']

class AdminRequired(RoleRequiredMixin):
    required_roles = ['admin']

# Usage
class PatientDetailView(CareNavigatorRequired, DetailView):
    model = Patient
```

---

## Conclusion: Key architectural decisions

This build specification addresses CareAtlas's operational challenges through a unified portal that:

**Consolidates fragmented workflows** by bringing device ordering, ticket management, vitals monitoring, and reporting into a single Django application with consistent UX patterns via HTMX + Alpine.js.

**Integrates deeply with Tenovi** through a rate-limited API client and webhook handlers that maintain real-time order and device status synchronization in the drop-ship fulfillment model.

**Prioritizes HIPAA compliance** with field-level PHI encryption, comprehensive audit logging, role-based access controls, and proper session management.

**Enables efficient care navigator workflows** through multi-step order creation, connectivity monitoring dashboards, automated ticket generation, and CPT-code-ready time tracking.

**Scales with MongoDB** using time-series collections for vitals data, hybrid embedding for frequently-accessed relationships, and proper indexing strategies for operational queries.

The phased implementation approach delivers core ordering functionality in weeks 1-3, then builds progressively toward a complete operational platform by week 12.