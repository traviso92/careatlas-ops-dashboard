"""
Tenovi device catalog and types.
"""

DEVICE_CATALOG = [
    {
        'type': 'blood_pressure',
        'name': 'Blood Pressure Monitor',
        'manufacturer': 'Tenovi',
        'model': 'BP-100',
        'description': 'Automatic upper arm blood pressure monitor with Bluetooth connectivity',
        'readings': ['systolic', 'diastolic', 'pulse', 'irregular_heartbeat'],
        'icon': 'heart',
    },
    {
        'type': 'weight_scale',
        'name': 'Digital Weight Scale',
        'manufacturer': 'Tenovi',
        'model': 'WS-200',
        'description': 'High-precision digital scale with body composition analysis',
        'readings': ['weight_lbs', 'weight_kg', 'bmi'],
        'icon': 'scale',
    },
    {
        'type': 'blood_glucose',
        'name': 'Blood Glucose Meter',
        'manufacturer': 'Tenovi',
        'model': 'BG-300',
        'description': 'Blood glucose monitoring system with lancing device',
        'readings': ['glucose_mg_dl', 'meal_context'],
        'icon': 'droplet',
    },
    {
        'type': 'pulse_oximeter',
        'name': 'Pulse Oximeter',
        'manufacturer': 'Tenovi',
        'model': 'PO-400',
        'description': 'Fingertip pulse oximeter for SpO2 and pulse rate',
        'readings': ['spo2', 'pulse', 'perfusion_index'],
        'icon': 'activity',
    },
    {
        'type': 'thermometer',
        'name': 'Digital Thermometer',
        'manufacturer': 'Tenovi',
        'model': 'TH-500',
        'description': 'Non-contact infrared thermometer',
        'readings': ['temperature_f', 'temperature_c'],
        'icon': 'thermometer',
    },
    {
        'type': 'peak_flow',
        'name': 'Peak Flow Meter',
        'manufacturer': 'Tenovi',
        'model': 'PF-600',
        'description': 'Digital peak flow meter for asthma management',
        'readings': ['pef', 'fev1'],
        'icon': 'wind',
    },
]


def get_device_by_type(device_type: str) -> dict:
    """Get device info by type."""
    for device in DEVICE_CATALOG:
        if device['type'] == device_type:
            return device
    return None


def get_device_types() -> list:
    """Get list of device types."""
    return [d['type'] for d in DEVICE_CATALOG]


def get_device_choices():
    """Get device choices for forms."""
    return [(d['type'], d['name']) for d in DEVICE_CATALOG]
