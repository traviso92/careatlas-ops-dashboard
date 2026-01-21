"""
Vitals views.
"""
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from apps.core.models import serialize_doc
from .models import Vital


def patient_vitals(request, patient_id):
    """Get vitals for a patient."""
    device_type = request.GET.get('device_type', '')
    days = int(request.GET.get('days', 30))

    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    vitals = Vital.get_time_range(
        patient_id,
        start_date,
        end_date,
        device_type=device_type if device_type else None
    )

    vitals = [serialize_doc(v) for v in vitals]

    context = {
        'vitals': vitals,
        'patient_id': patient_id,
        'device_type': device_type,
        'days': days,
    }

    if request.htmx:
        return render(request, 'vitals/partials/vitals_table.html', context)

    return render(request, 'vitals/list.html', context)


def vitals_chart_data(request, patient_id):
    """Return vitals data for Chart.js."""
    device_type = request.GET.get('device_type', 'blood_pressure')
    days = int(request.GET.get('days', 30))

    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    vitals = Vital.get_time_range(
        patient_id,
        start_date,
        end_date,
        device_type=device_type
    )

    # Format data for Chart.js
    labels = []
    datasets = {}

    for vital in vitals:
        timestamp = vital.get('timestamp')
        if timestamp:
            labels.append(timestamp.isoformat())

        readings = vital.get('readings', {})
        for key, value in readings.items():
            if isinstance(value, (int, float)):
                if key not in datasets:
                    datasets[key] = []
                datasets[key].append(value)

    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': key.replace('_', ' ').title(),
                'data': values,
                'borderColor': get_chart_color(i),
                'fill': False,
            }
            for i, (key, values) in enumerate(datasets.items())
        ]
    }

    return JsonResponse(chart_data)


def get_chart_color(index: int) -> str:
    """Get a color for chart datasets."""
    colors = [
        '#3B82F6',  # Blue
        '#EF4444',  # Red
        '#10B981',  # Green
        '#F59E0B',  # Yellow
        '#8B5CF6',  # Purple
        '#EC4899',  # Pink
    ]
    return colors[index % len(colors)]


def latest_vitals(request, patient_id):
    """Get the latest vital of each type for a patient."""
    latest = Vital.get_latest_by_type(patient_id)

    # Serialize the results
    result = {}
    for device_type, vital in latest.items():
        result[device_type] = serialize_doc(vital)

    if request.htmx:
        return render(request, 'vitals/partials/latest_vitals.html', {
            'latest_vitals': result,
            'patient_id': patient_id,
        })

    return JsonResponse(result)
