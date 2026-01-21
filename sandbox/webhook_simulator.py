#!/usr/bin/env python
"""
Webhook simulator for testing Tenovi webhook endpoints.

Usage:
    python sandbox/webhook_simulator.py --type measurement --patient CA-001
    python sandbox/webhook_simulator.py --type fulfillment --order ORD-001 --status shipped
    python sandbox/webhook_simulator.py --type device_registration --serial BP-001-A1B2C3
"""
import argparse
import json
import os
import sys
import requests
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.patients.models import Patient
from apps.devices.models import Device
from apps.orders.models import Order
from integrations.tenovi.sandbox import SandboxGenerator


BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8000')


def send_measurement_webhook(patient_mrn: str, device_type: str = 'blood_pressure'):
    """Send a fake measurement webhook."""
    # Find patient
    patient = Patient.find_by_mrn(patient_mrn)
    if not patient:
        print(f"Error: Patient with MRN '{patient_mrn}' not found")
        return False

    patient_id = str(patient['_id'])

    # Find a device for this patient
    device = Device.find_one({
        'patient_id': patient_id,
        'device_type': device_type
    })

    # Generate fake reading
    payload = SandboxGenerator.fake_vital_reading(device_type, patient_id)

    if device:
        payload['device_id'] = device.get('hwi_device_id', SandboxGenerator.generate_device_id())

    # Send webhook
    url = f"{BASE_URL}/webhooks/tenovi/measurement/"
    print(f"Sending measurement webhook to {url}")
    print(f"Payload: {json.dumps(payload, indent=2, default=str)}")

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return False


def send_fulfillment_webhook(order_number: str, status: str):
    """Send a fake fulfillment webhook."""
    # Find order
    order = Order.find_by_order_number(order_number)
    if not order:
        print(f"Error: Order '{order_number}' not found")
        return False

    vendor_order_id = order.get('vendor_order_id')
    if not vendor_order_id:
        vendor_order_id = SandboxGenerator.generate_order_id()

    payload = {
        'event_type': 'fulfillment',
        'order_id': vendor_order_id,
        'status': status,
    }

    if status == 'shipped':
        payload['tracking_number'] = SandboxGenerator.generate_tracking_number()
        payload['tracking_url'] = f"https://track.example.com/{payload['tracking_number']}"
        payload['shipped_at'] = datetime.utcnow().isoformat()

    if status == 'delivered':
        payload['delivered_at'] = datetime.utcnow().isoformat()

    # Send webhook
    url = f"{BASE_URL}/webhooks/tenovi/fulfillment/"
    print(f"Sending fulfillment webhook to {url}")
    print(f"Payload: {json.dumps(payload, indent=2, default=str)}")

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return False


def send_device_registration_webhook(serial_number: str):
    """Send a fake device registration webhook."""
    # Find device
    device = Device.find_by_serial(serial_number)
    if not device:
        print(f"Error: Device with serial '{serial_number}' not found")
        return False

    payload = SandboxGenerator.fake_device_registration(
        serial_number=serial_number,
        device_type=device.get('device_type', 'blood_pressure'),
        patient_id=device.get('patient_id', '')
    )

    # Send webhook
    url = f"{BASE_URL}/webhooks/tenovi/device-registration/"
    print(f"Sending device registration webhook to {url}")
    print(f"Payload: {json.dumps(payload, indent=2, default=str)}")

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Simulate Tenovi webhooks')
    parser.add_argument('--type', required=True,
                        choices=['measurement', 'fulfillment', 'device_registration'],
                        help='Type of webhook to send')
    parser.add_argument('--patient', help='Patient MRN (for measurement)')
    parser.add_argument('--device-type', default='blood_pressure',
                        choices=['blood_pressure', 'weight_scale', 'blood_glucose',
                                'pulse_oximeter', 'thermometer'],
                        help='Device type (for measurement)')
    parser.add_argument('--order', help='Order number (for fulfillment)')
    parser.add_argument('--status', default='shipped',
                        choices=['processing', 'shipped', 'delivered', 'cancelled'],
                        help='Order status (for fulfillment)')
    parser.add_argument('--serial', help='Device serial number (for device_registration)')
    parser.add_argument('--url', default='http://localhost:8000',
                        help='Base URL for webhooks')

    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.url

    if args.type == 'measurement':
        if not args.patient:
            print("Error: --patient is required for measurement webhooks")
            sys.exit(1)
        success = send_measurement_webhook(args.patient, args.device_type)

    elif args.type == 'fulfillment':
        if not args.order:
            print("Error: --order is required for fulfillment webhooks")
            sys.exit(1)
        success = send_fulfillment_webhook(args.order, args.status)

    elif args.type == 'device_registration':
        if not args.serial:
            print("Error: --serial is required for device_registration webhooks")
            sys.exit(1)
        success = send_device_registration_webhook(args.serial)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
