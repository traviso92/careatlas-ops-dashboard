"""
Order views.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from apps.core.models import serialize_doc
from apps.core.middleware import add_toast
from apps.patients.models import Patient
from .models import Order
from .services import OrderService


def order_list(request):
    """List orders with search and filter."""
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    page = int(request.GET.get('page', 1))
    per_page = 20

    orders = Order.search(
        query=query if query else None,
        status=status if status else None,
        limit=per_page,
        skip=(page - 1) * per_page
    )

    # Get total count for pagination
    filter_query = {}
    if query:
        filter_query['$or'] = [
            {'order_number': {'$regex': query, '$options': 'i'}},
            {'vendor_order_id': {'$regex': query, '$options': 'i'}},
        ]
    if status:
        filter_query['status'] = status

    total = Order.count(filter_query)

    orders = [serialize_doc(o) for o in orders]

    # Enrich with patient info
    for order in orders:
        if order.get('patient_id'):
            patient = Patient.find_by_id(order['patient_id'])
            if patient:
                order['patient'] = serialize_doc(patient)

    total_pages = (total + per_page - 1) // per_page

    # Get status counts for filters
    status_counts = Order.count_by_status()

    context = {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'status_counts': status_counts,
        'query': query,
        'current_status': status,
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    if request.htmx:
        return render(request, 'orders/partials/order_table.html', context)

    return render(request, 'orders/list.html', context)


def order_detail(request, order_id):
    """Order detail view."""
    order = Order.find_by_id(order_id)

    if not order:
        return HttpResponse('Order not found', status=404)

    # Get patient info
    patient = None
    if order.get('patient_id'):
        patient = Patient.find_by_id(order['patient_id'])
        if patient:
            patient = serialize_doc(patient)

    context = {
        'order': serialize_doc(order),
        'patient': patient,
        'status_choices': Order.STATUS_CHOICES,
    }

    return render(request, 'orders/detail.html', context)


def order_create(request):
    """Multi-step order creation form."""
    step = request.GET.get('step', '1')

    if step == '1':
        # Step 1: Search/select patient
        return render(request, 'orders/partials/create_step1.html')

    elif step == '2':
        # Step 2: Select devices
        patient_id = request.GET.get('patient_id')
        if not patient_id:
            add_toast(request, 'Please select a patient first', 'error')
            return render(request, 'orders/partials/create_step1.html')

        patient = Patient.find_by_id(patient_id)
        if not patient:
            add_toast(request, 'Patient not found', 'error')
            return render(request, 'orders/partials/create_step1.html')

        from integrations.tenovi.device_types import DEVICE_CATALOG

        context = {
            'patient': serialize_doc(patient),
            'device_types': DEVICE_CATALOG,
        }
        return render(request, 'orders/partials/create_step2.html', context)

    elif step == '3':
        # Step 3: Confirm shipping address
        patient_id = request.GET.get('patient_id')
        devices = request.GET.getlist('devices')

        if not patient_id:
            add_toast(request, 'Please select a patient first', 'error')
            return render(request, 'orders/partials/create_step1.html')

        if not devices:
            add_toast(request, 'Please select at least one device', 'error')
            patient = Patient.find_by_id(patient_id)
            from integrations.tenovi.device_types import DEVICE_CATALOG
            context = {
                'patient': serialize_doc(patient) if patient else {},
                'device_types': DEVICE_CATALOG,
            }
            return render(request, 'orders/partials/create_step2.html', context)

        patient = Patient.find_by_id(patient_id)
        if not patient:
            add_toast(request, 'Patient not found', 'error')
            return render(request, 'orders/partials/create_step1.html')

        from integrations.tenovi.device_types import DEVICE_CATALOG
        selected_devices = [d for d in DEVICE_CATALOG if d['type'] in devices]

        context = {
            'patient': serialize_doc(patient),
            'selected_devices': selected_devices,
            'address': patient.get('address', {}),
        }
        return render(request, 'orders/partials/create_step3.html', context)

    return render(request, 'orders/create.html')


@require_http_methods(['POST'])
def order_submit(request):
    """Submit the order."""
    patient_id = request.POST.get('patient_id')
    devices = request.POST.getlist('devices')
    notes = request.POST.get('notes', '')

    # Build shipping address from form
    shipping_address = {
        'name': request.POST.get('shipping_name', ''),
        'street': request.POST.get('shipping_street', ''),
        'city': request.POST.get('shipping_city', ''),
        'state': request.POST.get('shipping_state', ''),
        'zip_code': request.POST.get('shipping_zip', ''),
    }

    # Build items list
    items = [{'device_type': d, 'quantity': 1} for d in devices]

    service = OrderService()
    try:
        order_id = service.create_order(
            patient_id=patient_id,
            items=items,
            shipping_address=shipping_address,
            notes=notes
        )
        add_toast(request, 'Order created successfully', 'success')

        if request.htmx:
            response = HttpResponse()
            response['HX-Redirect'] = f'/orders/{order_id}/'
            return response

        return redirect('order_detail', order_id=order_id)

    except ValueError as e:
        add_toast(request, str(e), 'error')
        return HttpResponse(str(e), status=400)


@require_http_methods(['POST'])
def order_cancel(request, order_id):
    """Cancel an order."""
    reason = request.POST.get('reason', '')

    service = OrderService()
    try:
        service.cancel_order(order_id, reason)
        add_toast(request, 'Order cancelled successfully', 'success')
    except ValueError as e:
        add_toast(request, str(e), 'error')
        return HttpResponse(str(e), status=400)

    if request.htmx:
        order = Order.find_by_id(order_id)
        return render(request, 'orders/partials/status_badge.html', {
            'order': serialize_doc(order)
        })

    return redirect('order_detail', order_id=order_id)


def pending_orders(request):
    """List pending orders that need attention."""
    orders = Order.get_pending_orders(limit=50)
    orders = [serialize_doc(o) for o in orders]

    # Enrich with patient info
    for order in orders:
        if order.get('patient_id'):
            patient = Patient.find_by_id(order['patient_id'])
            if patient:
                order['patient'] = serialize_doc(patient)

    context = {
        'orders': orders,
        'total': len(orders),
    }

    if request.htmx:
        return render(request, 'orders/partials/pending_list.html', context)

    return render(request, 'orders/pending.html', context)
