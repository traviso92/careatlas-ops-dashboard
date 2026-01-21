"""
Device views.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from apps.core.models import serialize_doc
from apps.core.middleware import add_toast
from .models import Device
from .services import DeviceService


def device_list(request):
    """List devices with search and filter."""
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    device_type = request.GET.get('device_type', '')
    page = int(request.GET.get('page', 1))
    per_page = 20

    devices = Device.search(
        query=query if query else None,
        status=status if status else None,
        device_type=device_type if device_type else None,
        limit=per_page,
        skip=(page - 1) * per_page
    )

    # Get total count for pagination
    filter_query = {}
    if query:
        filter_query['$or'] = [
            {'serial_number': {'$regex': query, '$options': 'i'}},
            {'hwi_device_id': {'$regex': query, '$options': 'i'}},
        ]
    if status:
        filter_query['status'] = status
    if device_type:
        filter_query['device_type'] = device_type

    total = Device.count(filter_query)

    devices = [serialize_doc(d) for d in devices]
    total_pages = (total + per_page - 1) // per_page

    # Get status counts for filters
    status_counts = Device.count_by_status()

    context = {
        'devices': devices,
        'status_choices': Device.STATUS_CHOICES,
        'status_counts': status_counts,
        'query': query,
        'current_status': status,
        'current_type': device_type,
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    if request.htmx:
        return render(request, 'devices/partials/device_table.html', context)

    return render(request, 'devices/list.html', context)


def device_detail(request, device_id):
    """Device detail view."""
    device = Device.find_by_id(device_id)

    if not device:
        return HttpResponse('Device not found', status=404)

    # Get patient info if assigned
    patient = None
    if device.get('patient_id'):
        from apps.patients.models import Patient
        patient = Patient.find_by_id(device['patient_id'])
        if patient:
            patient = serialize_doc(patient)

    # Get recent vitals from this device
    from apps.vitals.models import Vital
    vitals = Vital.find_by_device(device_id, limit=20)
    vitals = [serialize_doc(v) for v in vitals]

    context = {
        'device': serialize_doc(device),
        'patient': patient,
        'vitals': vitals,
        'status_choices': Device.STATUS_CHOICES,
    }

    return render(request, 'devices/detail.html', context)


@require_http_methods(['POST'])
def device_update_status(request, device_id):
    """Update device status."""
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')

    if new_status not in dict(Device.STATUS_CHOICES):
        return HttpResponse('Invalid status', status=400)

    Device.update_status(device_id, new_status, notes)
    add_toast(request, f'Device status updated to {new_status}', 'success')

    if request.htmx:
        device = Device.find_by_id(device_id)
        return render(request, 'devices/partials/status_badge.html', {
            'device': serialize_doc(device)
        })

    return redirect('device_detail', device_id=device_id)


@require_http_methods(['POST'])
def device_assign(request, device_id):
    """Assign device to a patient."""
    patient_id = request.POST.get('patient_id')

    if not patient_id:
        return HttpResponse('Patient ID required', status=400)

    service = DeviceService()
    try:
        service.assign_device(device_id, patient_id)
        add_toast(request, 'Device assigned successfully', 'success')
    except ValueError as e:
        add_toast(request, str(e), 'error')
        return HttpResponse(str(e), status=400)

    if request.htmx:
        response = HttpResponse()
        response['HX-Redirect'] = f'/devices/{device_id}/'
        return response

    return redirect('device_detail', device_id=device_id)


@require_http_methods(['POST'])
def device_return(request, device_id):
    """Process device return."""
    reason = request.POST.get('reason', '')

    service = DeviceService()
    try:
        service.return_device(device_id, reason)
        add_toast(request, 'Device returned successfully', 'success')
    except ValueError as e:
        add_toast(request, str(e), 'error')
        return HttpResponse(str(e), status=400)

    if request.htmx:
        response = HttpResponse()
        response['HX-Redirect'] = f'/devices/{device_id}/'
        return response

    return redirect('device_detail', device_id=device_id)


def offline_devices(request):
    """List offline devices that need attention."""
    service = DeviceService()
    devices = service.check_connectivity()
    devices = [serialize_doc(d) for d in devices]

    # Enrich with patient info
    for device in devices:
        if device.get('patient_id'):
            from apps.patients.models import Patient
            patient = Patient.find_by_id(device['patient_id'])
            if patient:
                device['patient'] = serialize_doc(patient)

    context = {
        'devices': devices,
        'total': len(devices),
    }

    if request.htmx:
        return render(request, 'devices/partials/offline_list.html', context)

    return render(request, 'devices/offline.html', context)
