"""
Custom template tags and filters for the CareAtlas Ops Dashboard.
"""
from django import template
from datetime import datetime

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)


@register.filter
def friendly_date(value):
    """
    Format a date string or datetime object in a friendly format.
    Usage: {{ date_value|friendly_date }}
    Returns: "Jan 21, 2026"
    """
    if not value:
        return "-"

    if isinstance(value, str):
        try:
            # Try to parse ISO format
            if 'T' in value:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                value = datetime.strptime(value[:10], '%Y-%m-%d')
        except (ValueError, AttributeError):
            return value

    if isinstance(value, datetime):
        return value.strftime('%b %d, %Y')

    return str(value)


@register.filter
def friendly_datetime(value):
    """
    Format a datetime in a friendly format with time.
    Usage: {{ datetime_value|friendly_datetime }}
    Returns: "Jan 21, 2026 at 2:30 PM"
    """
    if not value:
        return "-"

    if isinstance(value, str):
        try:
            if 'T' in value:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                value = datetime.strptime(value[:16], '%Y-%m-%d %H:%M')
        except (ValueError, AttributeError):
            return value

    if isinstance(value, datetime):
        return value.strftime('%b %d, %Y at %I:%M %p')

    return str(value)


@register.filter
def device_type_display(value):
    """
    Convert device type slug to display name.
    Usage: {{ device.device_type|device_type_display }}
    """
    type_map = {
        'blood_pressure': 'Blood Pressure Monitor',
        'weight_scale': 'Weight Scale',
        'blood_glucose': 'Blood Glucose Monitor',
        'pulse_oximeter': 'Pulse Oximeter',
        'thermometer': 'Thermometer',
    }
    return type_map.get(value, value.replace('_', ' ').title() if value else '-')
