"""
Dashboard views.
"""
from django.shortcuts import render
from apps.core.models import serialize_doc
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.devices.models import Device
from apps.devices.services import DeviceService
from apps.patients.models import Patient


def dashboard(request):
    """Main dashboard view."""
    # Get statistics
    order_service = OrderService()
    device_service = DeviceService()

    order_stats = order_service.get_order_stats()
    device_stats = device_service.get_device_stats()

    # Get recent orders
    recent_orders = Order.get_recent(limit=5)
    recent_orders = [serialize_doc(o) for o in recent_orders]

    # Enrich orders with patient info
    for order in recent_orders:
        if order.get('patient_id'):
            patient = Patient.find_by_id(order['patient_id'])
            if patient:
                order['patient'] = serialize_doc(patient)

    # Get offline devices
    offline_devices = device_service.check_connectivity()[:5]
    offline_devices = [serialize_doc(d) for d in offline_devices]

    # Enrich offline devices with patient info
    for device in offline_devices:
        if device.get('patient_id'):
            patient = Patient.find_by_id(device['patient_id'])
            if patient:
                device['patient'] = serialize_doc(patient)

    # Get total patient count
    patient_count = Patient.count({'status': 'active'})

    context = {
        'order_stats': order_stats,
        'device_stats': device_stats,
        'recent_orders': recent_orders,
        'offline_devices': offline_devices,
        'patient_count': patient_count,
    }

    return render(request, 'dashboard/index.html', context)


def dashboard_stats(request):
    """HTMX endpoint for refreshing dashboard stats."""
    order_service = OrderService()
    device_service = DeviceService()

    context = {
        'order_stats': order_service.get_order_stats(),
        'device_stats': device_service.get_device_stats(),
        'patient_count': Patient.count({'status': 'active'}),
    }

    return render(request, 'dashboard/partials/stats.html', context)


def dashboard_recent_orders(request):
    """HTMX endpoint for recent orders table."""
    recent_orders = Order.get_recent(limit=5)
    recent_orders = [serialize_doc(o) for o in recent_orders]

    for order in recent_orders:
        if order.get('patient_id'):
            patient = Patient.find_by_id(order['patient_id'])
            if patient:
                order['patient'] = serialize_doc(patient)

    return render(request, 'dashboard/partials/recent_orders.html', {
        'recent_orders': recent_orders
    })


def dashboard_offline_devices(request):
    """HTMX endpoint for offline devices alert."""
    device_service = DeviceService()
    offline_devices = device_service.check_connectivity()[:5]
    offline_devices = [serialize_doc(d) for d in offline_devices]

    for device in offline_devices:
        if device.get('patient_id'):
            patient = Patient.find_by_id(device['patient_id'])
            if patient:
                device['patient'] = serialize_doc(patient)

    return render(request, 'dashboard/partials/offline_devices.html', {
        'offline_devices': offline_devices
    })


def dashboard_offline_device_count(request):
    """HTMX endpoint for offline device count badge in sidebar."""
    from django.http import HttpResponse
    device_service = DeviceService()
    offline_devices = device_service.check_connectivity()
    count = len(offline_devices)
    return HttpResponse(str(count))


def global_search(request):
    """Global search across patients and orders."""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return render(request, 'dashboard/partials/search_results.html', {
            'patients': [],
            'orders': [],
            'query': '',
        })

    # Search patients
    patients = Patient.search(query=query, limit=5)
    patients = [serialize_doc(p) for p in patients]

    # Search orders
    orders = Order.search(query=query, limit=5)
    orders = [serialize_doc(o) for o in orders]

    # Enrich orders with patient info
    for order in orders:
        if order.get('patient_id'):
            patient = Patient.find_by_id(order['patient_id'])
            if patient:
                order['patient'] = serialize_doc(patient)

    context = {
        'patients': patients,
        'orders': orders,
        'query': query,
        'has_results': bool(patients or orders),
    }

    return render(request, 'dashboard/partials/search_results.html', context)
