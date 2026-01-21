"""
Sandbox fake data generators for Tenovi API responses.
"""
import random
import uuid
from datetime import datetime, timedelta


class SandboxGenerator:
    """Generate fake Tenovi API responses for sandbox mode."""

    @staticmethod
    def generate_order_id() -> str:
        """Generate a fake Tenovi order ID."""
        return f"TNV-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def generate_device_id() -> str:
        """Generate a fake Tenovi device ID."""
        return f"HWI-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def generate_tracking_number() -> str:
        """Generate a fake tracking number."""
        carriers = ['1Z', '94', '92']
        prefix = random.choice(carriers)
        return f"{prefix}{random.randint(100000000000, 999999999999)}"

    @staticmethod
    def fake_order_response(patient_id: str, items: list, order_reference: str = None) -> dict:
        """Generate a fake order creation response."""
        return {
            'order_id': SandboxGenerator.generate_order_id(),
            'status': 'processing',
            'patient_id': patient_id,
            'order_reference': order_reference,
            'items': items,
            'estimated_delivery': (datetime.utcnow() + timedelta(days=random.randint(3, 7))).isoformat(),
            'created_at': datetime.utcnow().isoformat(),
        }

    @staticmethod
    def fake_order_status(order_id: str, status: str = None) -> dict:
        """Generate a fake order status response."""
        if status is None:
            status = random.choice(['processing', 'shipped', 'delivered'])

        response = {
            'order_id': order_id,
            'status': status,
            'updated_at': datetime.utcnow().isoformat(),
        }

        if status == 'shipped':
            response['tracking_number'] = SandboxGenerator.generate_tracking_number()
            response['tracking_url'] = f"https://track.example.com/{response['tracking_number']}"
            response['shipped_at'] = datetime.utcnow().isoformat()

        if status == 'delivered':
            response['delivered_at'] = datetime.utcnow().isoformat()

        return response

    @staticmethod
    def fake_vital_reading(device_type: str, patient_id: str = None) -> dict:
        """Generate a fake vital reading."""
        readings = {
            'blood_pressure': {
                'systolic': random.randint(100, 160),
                'diastolic': random.randint(60, 100),
                'pulse': random.randint(55, 100),
                'irregular': random.random() < 0.05,
            },
            'weight_scale': {
                'weight_lbs': round(random.uniform(120, 280), 1),
                'weight_kg': round(random.uniform(54, 127), 1),
            },
            'blood_glucose': {
                'glucose_mg_dl': random.randint(70, 200),
                'meal_context': random.choice(['fasting', 'before_meal', 'after_meal']),
            },
            'pulse_oximeter': {
                'spo2': random.randint(92, 100),
                'pulse': random.randint(55, 100),
                'perfusion_index': round(random.uniform(0.5, 10.0), 1),
            },
            'thermometer': {
                'temperature_f': round(random.uniform(97.0, 101.0), 1),
                'temperature_c': round(random.uniform(36.1, 38.3), 1),
            },
            'peak_flow': {
                'pef': random.randint(300, 700),
                'fev1': round(random.uniform(1.5, 5.0), 2),
            },
        }

        return {
            'event_type': 'measurement',
            'device_id': SandboxGenerator.generate_device_id(),
            'patient_id': patient_id,
            'device_type': device_type,
            'timestamp': datetime.utcnow().isoformat(),
            'readings': readings.get(device_type, {}),
            'metadata': {
                'battery_level': random.randint(20, 100),
                'signal_strength': random.randint(-80, -40),
            }
        }

    @staticmethod
    def fake_device_registration(serial_number: str, device_type: str, patient_id: str) -> dict:
        """Generate a fake device registration response."""
        return {
            'device_id': SandboxGenerator.generate_device_id(),
            'serial_number': serial_number,
            'device_type': device_type,
            'patient_id': patient_id,
            'status': 'active',
            'registered_at': datetime.utcnow().isoformat(),
        }
