"""
Ticket views.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from apps.core.models import serialize_doc
from apps.core.middleware import add_toast
from apps.patients.models import Patient
from apps.devices.models import Device
from apps.orders.models import Order
from .models import Ticket


def ticket_list(request):
    """List tickets with search and filter."""
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    category = request.GET.get('category', '')
    page = int(request.GET.get('page', 1))
    per_page = 20

    tickets = Ticket.search(
        query=query if query else None,
        status=status if status else None,
        priority=priority if priority else None,
        category=category if category else None,
        limit=per_page,
        skip=(page - 1) * per_page
    )

    # Get total count for pagination
    filter_query = {}
    if query:
        filter_query['$or'] = [
            {'ticket_number': {'$regex': query, '$options': 'i'}},
            {'title': {'$regex': query, '$options': 'i'}},
        ]
    if status:
        filter_query['status'] = status
    if priority:
        filter_query['priority'] = priority
    if category:
        filter_query['category'] = category

    total = Ticket.count(filter_query)

    tickets = [serialize_doc(t) for t in tickets]
    total_pages = (total + per_page - 1) // per_page

    # Get status counts for filters
    status_counts = Ticket.count_by_status()

    context = {
        'tickets': tickets,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'status_counts': status_counts,
        'query': query,
        'current_status': status,
        'current_priority': priority,
        'current_category': category,
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    if request.htmx:
        return render(request, 'tickets/partials/ticket_table.html', context)

    return render(request, 'tickets/list.html', context)


def ticket_detail(request, ticket_id):
    """Ticket detail view."""
    ticket = Ticket.find_by_id(ticket_id)

    if not ticket:
        return HttpResponse('Ticket not found', status=404)

    ticket = serialize_doc(ticket)

    # Get related entities
    patient = None
    device = None
    order = None

    if ticket.get('patient_id'):
        patient = Patient.find_by_id(ticket['patient_id'])
        if patient:
            patient = serialize_doc(patient)

    if ticket.get('device_id'):
        device = Device.find_by_id(ticket['device_id'])
        if device:
            device = serialize_doc(device)

    if ticket.get('order_id'):
        order = Order.find_by_id(ticket['order_id'])
        if order:
            order = serialize_doc(order)

    context = {
        'ticket': ticket,
        'patient': patient,
        'device': device,
        'order': order,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
    }

    return render(request, 'tickets/detail.html', context)


@require_http_methods(['GET', 'POST'])
def ticket_create(request):
    """Create a new ticket."""
    if request.method == 'POST':
        data = {
            'title': request.POST.get('title'),
            'description': request.POST.get('description'),
            'priority': request.POST.get('priority', Ticket.PRIORITY_MEDIUM),
            'category': request.POST.get('category', Ticket.CATEGORY_OTHER),
            'patient_id': request.POST.get('patient_id') or None,
            'device_id': request.POST.get('device_id') or None,
            'order_id': request.POST.get('order_id') or None,
        }

        try:
            ticket_id = Ticket.create(data)
            add_toast(request, 'Ticket created successfully', 'success')

            if request.htmx:
                response = HttpResponse()
                response['HX-Redirect'] = f'/tickets/{ticket_id}/'
                return response

            return redirect('ticket_detail', ticket_id=ticket_id)
        except Exception as e:
            add_toast(request, str(e), 'error')

    # Pre-fill from query params (for creating from alerts)
    context = {
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'category_choices': Ticket.CATEGORY_CHOICES,
        'prefill_device_id': request.GET.get('device_id'),
        'prefill_patient_id': request.GET.get('patient_id'),
        'prefill_order_id': request.GET.get('order_id'),
        'prefill_category': request.GET.get('category', Ticket.CATEGORY_OTHER),
    }

    # Get prefill entity names
    if context['prefill_device_id']:
        device = Device.find_by_id(context['prefill_device_id'])
        if device:
            context['prefill_device'] = serialize_doc(device)

    if context['prefill_patient_id']:
        patient = Patient.find_by_id(context['prefill_patient_id'])
        if patient:
            context['prefill_patient'] = serialize_doc(patient)

    return render(request, 'tickets/create.html', context)


@require_http_methods(['POST'])
def ticket_add_message(request, ticket_id):
    """Add a message to a ticket."""
    content = request.POST.get('message')
    is_internal = request.POST.get('is_internal') == 'on'

    if not content:
        add_toast(request, 'Message cannot be empty', 'error')
        return redirect('ticket_detail', ticket_id=ticket_id)

    Ticket.add_message(ticket_id, content, 'Support', is_internal)
    add_toast(request, 'Message added', 'success')

    if request.htmx:
        ticket = Ticket.find_by_id(ticket_id)
        return render(request, 'tickets/partials/message_list.html', {
            'ticket': serialize_doc(ticket)
        })

    return redirect('ticket_detail', ticket_id=ticket_id)


@require_http_methods(['POST'])
def ticket_update_status(request, ticket_id):
    """Update ticket status."""
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')

    if new_status not in dict(Ticket.STATUS_CHOICES):
        return HttpResponse('Invalid status', status=400)

    Ticket.update_status(ticket_id, new_status, notes)
    add_toast(request, f'Ticket status updated to {new_status}', 'success')

    if request.htmx:
        ticket = Ticket.find_by_id(ticket_id)
        return render(request, 'tickets/partials/status_badge.html', {
            'ticket': serialize_doc(ticket)
        })

    return redirect('ticket_detail', ticket_id=ticket_id)
