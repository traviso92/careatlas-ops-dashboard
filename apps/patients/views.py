"""
Patient views.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from apps.core.models import serialize_doc
from apps.core.middleware import add_toast
from .models import Patient
from .forms import PatientForm, PatientSearchForm


def patient_list(request):
    """List patients with search and filter."""
    form = PatientSearchForm(request.GET)

    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    program = request.GET.get('program', '')
    page = int(request.GET.get('page', 1))
    per_page = 20

    patients = Patient.search(
        query=query if query else None,
        status=status if status else None,
        program=program if program else None,
        limit=per_page,
        skip=(page - 1) * per_page
    )

    total = Patient.count({
        **({'$or': [
            {'mrn': {'$regex': query, '$options': 'i'}},
            {'first_name': {'$regex': query, '$options': 'i'}},
            {'last_name': {'$regex': query, '$options': 'i'}},
        ]} if query else {}),
        **({'status': status} if status else {}),
        **({'program': program} if program else {}),
    })

    patients = [serialize_doc(p) for p in patients]
    total_pages = (total + per_page - 1) // per_page

    context = {
        'patients': patients,
        'form': form,
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'query': query,
        'current_status': status,
        'current_program': program,
    }

    if request.htmx:
        return render(request, 'patients/partials/patient_table.html', context)

    return render(request, 'patients/list.html', context)


def patient_detail(request, patient_id):
    """Patient detail view."""
    patient = Patient.get_with_devices(patient_id)

    if not patient:
        return HttpResponse('Patient not found', status=404)

    # Get vitals for this patient
    from apps.vitals.models import Vital
    vitals = Vital.get_recent(patient_id, limit=50)
    vitals = [serialize_doc(v) for v in vitals]

    # Get orders for this patient
    from apps.orders.models import Order
    orders = Order.find_by_patient(patient_id, limit=10)
    orders = [serialize_doc(o) for o in orders]

    context = {
        'patient': serialize_doc(patient),
        'vitals': vitals,
        'orders': orders,
    }

    return render(request, 'patients/detail.html', context)


@require_http_methods(['GET', 'POST'])
def patient_create(request):
    """Create a new patient."""
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # Handle conditions as list
            if data.get('conditions'):
                data['conditions'] = [c.strip() for c in data['conditions'].split(',')]
            else:
                data['conditions'] = []

            patient_id = Patient.create(data)
            add_toast(request, 'Patient created successfully', 'success')

            if request.htmx:
                response = HttpResponse()
                response['HX-Redirect'] = f'/patients/{patient_id}/'
                return response

            return redirect('patient_detail', patient_id=patient_id)
    else:
        form = PatientForm()

    context = {'form': form, 'title': 'Create Patient'}

    if request.htmx:
        return render(request, 'patients/partials/patient_form.html', context)

    return render(request, 'patients/create.html', context)


@require_http_methods(['GET', 'POST'])
def patient_edit(request, patient_id):
    """Edit a patient."""
    patient = Patient.find_by_id(patient_id)
    if not patient:
        return HttpResponse('Patient not found', status=404)

    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if data.get('conditions'):
                data['conditions'] = [c.strip() for c in data['conditions'].split(',')]
            else:
                data['conditions'] = []

            # Update address nested structure
            data['address'] = {
                'street': data.pop('street', ''),
                'city': data.pop('city', ''),
                'state': data.pop('state', ''),
                'zip_code': data.pop('zip_code', ''),
            }

            Patient.update(patient_id, data)
            add_toast(request, 'Patient updated successfully', 'success')

            if request.htmx:
                response = HttpResponse()
                response['HX-Redirect'] = f'/patients/{patient_id}/'
                return response

            return redirect('patient_detail', patient_id=patient_id)
    else:
        # Pre-fill form with existing data
        initial = {
            'mrn': patient.get('mrn'),
            'first_name': patient.get('first_name'),
            'last_name': patient.get('last_name'),
            'dob': patient.get('dob'),
            'email': patient.get('email'),
            'phone': patient.get('phone'),
            'street': patient.get('address', {}).get('street'),
            'city': patient.get('address', {}).get('city'),
            'state': patient.get('address', {}).get('state'),
            'zip_code': patient.get('address', {}).get('zip_code'),
            'program': patient.get('program'),
            'conditions': ', '.join(patient.get('conditions', [])),
        }
        form = PatientForm(initial=initial)

    context = {
        'form': form,
        'patient': serialize_doc(patient),
        'title': 'Edit Patient'
    }

    if request.htmx:
        return render(request, 'patients/partials/patient_form.html', context)

    return render(request, 'patients/edit.html', context)


def patient_search_api(request):
    """API endpoint for patient search (used in order forms)."""
    query = request.GET.get('q', '')

    if len(query) < 2:
        return render(request, 'patients/partials/search_results.html', {'patients': [], 'query': ''})

    patients = Patient.search(query=query, limit=10)
    patients = [serialize_doc(p) for p in patients]

    return render(request, 'patients/partials/search_results.html', {'patients': patients, 'query': query})
