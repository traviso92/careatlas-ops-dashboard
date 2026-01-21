"""
Device services for business logic.
"""
from datetime import datetime
from .models import Device
from integrations.tenovi.client import TenoviClient


class DeviceService:
    """Service class for device operations."""

    def __init__(self):
        self.tenovi = TenoviClient()

    def provision_device(self, serial_number: str, device_type: str, patient_id: str = None):
        """
        Provision a new device, optionally assigning to a patient.
        """
        # Check if device already exists
        existing = Device.find_by_serial(serial_number)
        if existing:
            raise ValueError(f'Device with serial {serial_number} already exists')

        # Create device in our system
        device_data = {
            'serial_number': serial_number,
            'device_type': device_type,
            'status': Device.STATUS_INVENTORY,
        }

        if patient_id:
            device_data['patient_id'] = patient_id
            device_data['status'] = Device.STATUS_ASSIGNED
            device_data['assigned_at'] = datetime.utcnow()

        device_id = Device.create(device_data)

        # If assigned to patient, add to patient's device list
        if patient_id:
            from apps.patients.models import Patient
            Patient.add_device(patient_id, str(device_id))

        return device_id

    def assign_device(self, device_id: str, patient_id: str):
        """
        Assign a device to a patient.
        """
        device = Device.find_by_id(device_id)
        if not device:
            raise ValueError('Device not found')

        if device.get('patient_id'):
            raise ValueError('Device is already assigned to a patient')

        Device.assign_to_patient(device_id, patient_id)

        # TODO: When sandbox mode is off, register device with Tenovi
        # self.tenovi.register_device(device, patient)

        return True

    def return_device(self, device_id: str, reason: str = None):
        """
        Process a device return.
        """
        device = Device.find_by_id(device_id)
        if not device:
            raise ValueError('Device not found')

        Device.unassign_from_patient(device_id)
        Device.update_status(device_id, Device.STATUS_RETURNED, reason)

        return True

    def mark_lost(self, device_id: str, notes: str = None):
        """
        Mark a device as lost.
        """
        device = Device.find_by_id(device_id)
        if not device:
            raise ValueError('Device not found')

        if device.get('patient_id'):
            Device.unassign_from_patient(device_id)

        Device.update_status(device_id, Device.STATUS_LOST, notes)

        return True

    def check_connectivity(self):
        """
        Check all assigned devices for connectivity issues.
        Returns list of offline devices sorted by days offline (most critical first).
        """
        from datetime import datetime, timedelta

        offline_devices = list(Device.get_offline_devices(threshold_days=3))

        # Calculate days offline for each device and add severity
        now = datetime.utcnow()
        for device in offline_devices:
            last_reading = device.get('last_reading_at')
            if last_reading:
                delta = now - last_reading
                device['days_offline'] = delta.days
            else:
                # Never had a reading, assume assigned_at or created_at as reference
                ref_date = device.get('assigned_at') or device.get('created_at') or now
                delta = now - ref_date
                device['days_offline'] = delta.days

            # Set severity level
            if device['days_offline'] >= 7:
                device['severity'] = 'critical'
            elif device['days_offline'] >= 3:
                device['severity'] = 'warning'
            else:
                device['severity'] = 'info'

        # Sort by days offline (most critical first)
        offline_devices.sort(key=lambda d: d.get('days_offline', 0), reverse=True)

        return offline_devices

    def get_device_stats(self):
        """
        Get device statistics.
        """
        status_counts = Device.count_by_status()
        offline_count = len(self.check_connectivity())

        return {
            'total': sum(status_counts.values()),
            'by_status': status_counts,
            'offline_alerts': offline_count,
        }
