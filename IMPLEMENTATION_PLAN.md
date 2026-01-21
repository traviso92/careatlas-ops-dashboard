# CareAtlas Device Management Portal - Implementation Plan

## Overview

Building a Django + HTMX device management portal for RPM operations, integrating with Tenovi's drop-ship ecosystem.

**Tech Stack:**
- Django 5.1 + django-mongodb-backend
- HTMX 2.0 + Alpine.js 3.x
- Tailwind CSS + DaisyUI 4.x
- MongoDB (time-series for vitals)
- Celery + Redis (background tasks)

---

## Tonight's Build Scope (MVP)

### Phase 1: Foundation (First Priority)

```
ops-dashboard/
├── config/                 # Django settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/              # Shared utilities
│   ├── patients/          # Patient management
│   ├── devices/           # Device lifecycle
│   ├── orders/            # Order management
│   ├── vitals/            # Vitals data
│   ├── tickets/           # Support tickets (Phase 2)
│   ├── webhooks/          # Tenovi webhook handlers
│   └── dashboard/         # Main dashboard
├── integrations/
│   └── tenovi/            # Tenovi API client
├── templates/
│   ├── base.html
│   ├── components/
│   └── [app]/partials/
├── static/
├── sandbox/               # Fake data & simulators
│   ├── data/
│   └── webhook_simulator.py
├── manage.py
└── requirements.txt
```

### Data Models (MongoDB Collections)

1. **patients** - Core patient records with embedded device assignments
2. **devices** - Device lifecycle with status history
3. **orders** - Fulfillment tracking with Tenovi integration
4. **vitals** - Time-series collection for readings
5. **webhook_events** - Append-only event log (TTL indexed)
6. **audit_logs** - HIPAA-compliant activity tracking

### Tenovi Integration Points

| Endpoint | Purpose | Tonight's Status |
|----------|---------|------------------|
| `/hwi/hwi-devices/` | Device ordering | Sandbox mock |
| `/hwi/hwi-device-types/` | Available devices | Static data |
| `/hwi/hwi-patients/` | Patient sync | Sandbox mock |
| Measurement webhook | Vitals ingestion | Ready to receive |
| Fulfillment webhook | Order status | Ready to receive |

### Sandbox Mode Strategy

```python
# integrations/tenovi/client.py
class TenoviAPIClient:
    def __init__(self, sandbox_mode=True):
        self.sandbox_mode = sandbox_mode
        if sandbox_mode:
            self.base_url = None  # Use fake responses
        else:
            self.base_url = settings.TENOVI_BASE_URL
```

**Sandbox provides:**
- Fake device types with realistic data
- Mock order creation returning fake hwi_device_ids
- Webhook simulator to test event handling
- 50+ fake patients with varied conditions

---

## Implementation Sequence (Tonight)

### Step 1: Project Setup (~20 min)
- [x] Create Django project
- [x] Configure MongoDB connection
- [x] Set up Tailwind + DaisyUI via CDN
- [x] Install HTMX + Alpine.js
- [x] Create requirements.txt

### Step 2: Core Models (~30 min)
- [ ] Patient model with PHI fields
- [ ] Device model with status machine
- [ ] Order model with status tracking
- [ ] Vitals time-series setup
- [ ] WebhookEvent for logging

### Step 3: Tenovi Integration (~30 min)
- [ ] TenoviAPIClient with sandbox mode
- [ ] Device type catalog (static)
- [ ] Order creation mock
- [ ] Webhook signature validation
- [ ] Webhook handlers (measurement + fulfillment)

### Step 4: Base UI (~30 min)
- [ ] base.html with DaisyUI layout
- [ ] Sidebar navigation
- [ ] Toast notifications (Alpine.js)
- [ ] Modal container
- [ ] Loading indicators

### Step 5: Patient Views (~30 min)
- [ ] Patient list with search/filter
- [ ] Patient detail view
- [ ] Patient create/edit forms
- [ ] Device assignment display

### Step 6: Device Views (~30 min)
- [ ] Device list with status filters
- [ ] Device detail with history
- [ ] Connectivity status indicators
- [ ] Assignment management

### Step 7: Order Workflow (~40 min)
- [ ] Order list view
- [ ] Multi-step order creation (HTMX)
- [ ] Patient search + selection
- [ ] Device type selection
- [ ] Shipping confirmation
- [ ] Order status tracking

### Step 8: Dashboard (~20 min)
- [ ] Stats cards (orders, devices, alerts)
- [ ] Recent orders table
- [ ] Connectivity alerts
- [ ] Quick actions

### Step 9: Sandbox Data (~20 min)
- [ ] Fake patient generator
- [ ] Fake device inventory
- [ ] Fake order history
- [ ] Vitals data seeder
- [ ] Webhook simulator script

---

## Environment Variables Needed

```bash
# .env
DEBUG=True
SECRET_KEY=your-secret-key-here
MONGODB_URI=mongodb://localhost:27017/careatlas_ops

# Tenovi (for production)
TENOVI_API_KEY=your-api-key
TENOVI_CLIENT_DOMAIN=careatlas
TENOVI_WEBHOOK_SECRET=webhook-secret

# Feature flags
TENOVI_SANDBOX_MODE=true
```

---

## Key Design Decisions

1. **Sandbox-First**: All Tenovi interactions mocked initially, flip `TENOVI_SANDBOX_MODE=false` for production

2. **Webhook-Ready**: Endpoints exist and log all events, even in sandbox mode

3. **HTMX Partials**: Every view has a full-page version and HTMX partial for dynamic updates

4. **No JS Build**: Using CDN for Tailwind/DaisyUI/HTMX/Alpine - no npm needed tonight

5. **MongoDB Flexibility**: Using django-mongodb-backend for ORM compatibility with MongoDB

---

## Production Readiness Checklist (Future)

- [ ] PHI encryption at field level
- [ ] RBAC implementation
- [ ] Celery for background tasks
- [ ] Redis caching
- [ ] Rate limiting
- [ ] Audit log retention
- [ ] HIPAA security headers
- [ ] Sentry error tracking
- [ ] Health check endpoints

---

## Commands Reference

```bash
# Start development
cd /Users/travi/CareAtlas/ops-dashboard
source venv/bin/activate
python manage.py runserver

# Seed fake data
python manage.py seed_sandbox

# Simulate webhook
python sandbox/webhook_simulator.py --type measurement --count 10

# MongoDB shell
mongosh careatlas_ops
```

---

Ready to build?
