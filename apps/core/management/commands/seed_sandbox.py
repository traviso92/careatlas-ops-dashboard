"""
Management command to seed sandbox data.
"""
import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from apps.core.models import get_db
from apps.patients.models import Patient
from apps.devices.models import Device
from apps.orders.models import Order
from apps.vitals.models import Vital
from integrations.tenovi.sandbox import SandboxGenerator


class Command(BaseCommand):
    help = 'Seed the database with sandbox/fake data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--patients-only',
            action='store_true',
            help='Only seed patients',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.clear_data()

        self.stdout.write('Seeding sandbox data...')

        # Load JSON data
        base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'sandbox' / 'data'

        # Seed patients
        patients = self.seed_patients(base_path / 'patients.json')
        self.stdout.write(self.style.SUCCESS(f'  Created {len(patients)} patients'))

        if options['patients_only']:
            return

        # Seed devices
        devices = self.seed_devices(base_path / 'devices.json')
        self.stdout.write(self.style.SUCCESS(f'  Created {len(devices)} devices'))

        # Assign some devices to patients
        assignments = self.assign_devices(patients, devices)
        self.stdout.write(self.style.SUCCESS(f'  Assigned {assignments} devices to patients'))

        # Seed orders
        orders = self.seed_orders(patients)
        self.stdout.write(self.style.SUCCESS(f'  Created {len(orders)} orders'))

        # Seed vitals
        vitals = self.seed_vitals(patients, devices)
        self.stdout.write(self.style.SUCCESS(f'  Created {vitals} vital readings'))

        self.stdout.write(self.style.SUCCESS('Sandbox data seeded successfully!'))

    def clear_data(self):
        """Clear all existing data."""
        self.stdout.write('Clearing existing data...')
        db = get_db()
        db['patients'].delete_many({})
        db['devices'].delete_many({})
        db['orders'].delete_many({})
        db['vitals'].delete_many({})
        db['webhook_events'].delete_many({})
        self.stdout.write(self.style.WARNING('  Cleared all collections'))

    def seed_patients(self, filepath):
        """Seed patients from JSON file."""
        with open(filepath) as f:
            patients_data = json.load(f)

        patient_ids = []
        for data in patients_data:
            # Check if patient already exists
            existing = Patient.find_by_mrn(data['mrn'])
            if existing:
                patient_ids.append(str(existing['_id']))
                continue

            patient_id = Patient.create(data)
            patient_ids.append(str(patient_id))

        return patient_ids

    def seed_devices(self, filepath):
        """Seed devices from JSON file."""
        with open(filepath) as f:
            devices_data = json.load(f)

        device_ids = []
        for data in devices_data:
            # Check if device already exists
            existing = Device.find_by_serial(data['serial_number'])
            if existing:
                device_ids.append(str(existing['_id']))
                continue

            data['hwi_device_id'] = SandboxGenerator.generate_device_id()
            device_id = Device.create(data)
            device_ids.append(str(device_id))

        return device_ids

    def assign_devices(self, patient_ids, device_ids):
        """Assign devices to patients."""
        assignments = 0
        # Get available devices (in inventory)
        available_devices = Device.find({'status': Device.STATUS_INVENTORY}, limit=len(device_ids))

        for i, device in enumerate(available_devices):
            if i >= len(patient_ids):
                break

            # Assign 60% of devices
            if random.random() > 0.6:
                continue

            patient_id = patient_ids[i % len(patient_ids)]
            Device.assign_to_patient(device['_id'], patient_id)

            # Mark some as active (have reported readings)
            if random.random() > 0.3:
                last_reading = datetime.utcnow() - timedelta(hours=random.randint(1, 72))
                Device.record_reading(device['_id'], last_reading)

            assignments += 1

        return assignments

    def seed_orders(self, patient_ids):
        """Create sample orders."""
        order_ids = []
        statuses = [
            Order.STATUS_PENDING,
            Order.STATUS_PROCESSING,
            Order.STATUS_SHIPPED,
            Order.STATUS_DELIVERED,
            Order.STATUS_CANCELLED,
        ]

        device_types = ['blood_pressure', 'weight_scale', 'blood_glucose', 'pulse_oximeter']

        for i in range(30):
            patient_id = random.choice(patient_ids)
            patient = Patient.find_by_id(patient_id)

            if not patient:
                continue

            status = random.choice(statuses)
            items = [
                {'device_type': random.choice(device_types), 'quantity': 1}
                for _ in range(random.randint(1, 3))
            ]

            order_data = {
                'patient_id': patient_id,
                'items': items,
                'status': status,
                'shipping_address': {
                    'name': f"{patient.get('first_name', '')} {patient.get('last_name', '')}",
                    'street': patient.get('address', {}).get('street', ''),
                    'city': patient.get('address', {}).get('city', ''),
                    'state': patient.get('address', {}).get('state', ''),
                    'zip_code': patient.get('address', {}).get('zip_code', ''),
                },
                'vendor_order_id': SandboxGenerator.generate_order_id(),
            }

            order_id = Order.create(order_data)

            # Add tracking for shipped/delivered orders
            if status in [Order.STATUS_SHIPPED, Order.STATUS_DELIVERED]:
                Order.update(order_id, {
                    'tracking_number': SandboxGenerator.generate_tracking_number(),
                    'tracking_url': f'https://track.example.com/{SandboxGenerator.generate_tracking_number()}',
                    'shipped_at': datetime.utcnow() - timedelta(days=random.randint(1, 5)),
                })

            if status == Order.STATUS_DELIVERED:
                Order.update(order_id, {
                    'delivered_at': datetime.utcnow() - timedelta(days=random.randint(0, 3)),
                })

            order_ids.append(str(order_id))

        return order_ids

    def seed_vitals(self, patient_ids, device_ids):
        """Create sample vital readings."""
        vitals_count = 0

        # Get assigned devices
        assigned_devices = Device.find({
            'status': {'$in': [Device.STATUS_ACTIVE, Device.STATUS_ASSIGNED]},
            'patient_id': {'$ne': None}
        })

        for device in assigned_devices:
            device_type = device.get('device_type')
            patient_id = device.get('patient_id')

            if not device_type or not patient_id:
                continue

            # Create 10-20 readings per device over the last 30 days
            num_readings = random.randint(10, 20)

            # Generate unique timestamps by spreading readings evenly across the time range
            # and adding small random offsets
            used_timestamps = set()

            for i in range(num_readings):
                # Distribute readings across 30 days with unique timestamps
                base_offset_hours = (30 * 24 * i) // num_readings
                jitter_minutes = random.randint(0, 59)
                jitter_seconds = random.randint(0, 59)

                timestamp = datetime.utcnow() - timedelta(
                    hours=base_offset_hours,
                    minutes=jitter_minutes,
                    seconds=jitter_seconds
                )

                # Ensure unique timestamp
                while timestamp.isoformat() in used_timestamps:
                    timestamp = timestamp + timedelta(seconds=random.randint(1, 60))

                used_timestamps.add(timestamp.isoformat())

                reading_data = SandboxGenerator.fake_vital_reading(
                    device_type,
                    patient_id
                )

                Vital.create({
                    'patient_id': patient_id,
                    'device_id': str(device['_id']),
                    'device_type': device_type,
                    'timestamp': timestamp,
                    'readings': reading_data['readings'],
                    'metadata': reading_data['metadata'],
                    'source': 'sandbox_seeder',
                })

                vitals_count += 1

        return vitals_count
