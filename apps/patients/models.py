"""
Patient document model for MongoDB.
"""
from apps.core.models import BaseDocument, serialize_doc


class Patient(BaseDocument):
    """Patient document model."""

    collection_name = 'patients'

    @classmethod
    def create(cls, data: dict) -> str:
        """Create a new patient."""
        document = {
            'mrn': data['mrn'],
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'dob': data.get('dob'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'address': {
                'street': data.get('street', ''),
                'city': data.get('city', ''),
                'state': data.get('state', ''),
                'zip_code': data.get('zip_code', ''),
            },
            'devices': [],
            'program': data.get('program', 'RPM'),
            'care_navigator': data.get('care_navigator'),
            'conditions': data.get('conditions', []),
            'status': data.get('status', 'active'),
            'tenovi_patient_id': data.get('tenovi_patient_id'),
        }
        return cls.insert(document)

    @classmethod
    def search(cls, query: str = None, status: str = None, program: str = None,
               limit: int = 50, skip: int = 0):
        """Search patients with filters."""
        filter_query = {}

        if query:
            filter_query['$or'] = [
                {'mrn': {'$regex': query, '$options': 'i'}},
                {'first_name': {'$regex': query, '$options': 'i'}},
                {'last_name': {'$regex': query, '$options': 'i'}},
                {'email': {'$regex': query, '$options': 'i'}},
            ]

        if status:
            filter_query['status'] = status

        if program:
            filter_query['program'] = program

        return cls.find(
            filter_query,
            sort=[('last_name', 1), ('first_name', 1)],
            limit=limit,
            skip=skip
        )

    @classmethod
    def find_by_mrn(cls, mrn: str):
        """Find patient by MRN."""
        return cls.find_one({'mrn': mrn})

    @classmethod
    def add_device(cls, patient_id, device_id: str):
        """Add a device to patient's device list."""
        from bson import ObjectId
        if isinstance(patient_id, str):
            patient_id = ObjectId(patient_id)
        cls.get_collection().update_one(
            {'_id': patient_id},
            {'$addToSet': {'devices': device_id}}
        )

    @classmethod
    def remove_device(cls, patient_id, device_id: str):
        """Remove a device from patient's device list."""
        from bson import ObjectId
        if isinstance(patient_id, str):
            patient_id = ObjectId(patient_id)
        cls.get_collection().update_one(
            {'_id': patient_id},
            {'$pull': {'devices': device_id}}
        )

    @classmethod
    def get_with_devices(cls, patient_id):
        """Get patient with populated device information."""
        from apps.devices.models import Device
        patient = cls.find_by_id(patient_id)
        if patient and patient.get('devices'):
            patient['device_details'] = []
            for device_id in patient['devices']:
                device = Device.find_by_id(device_id)
                if device:
                    patient['device_details'].append(serialize_doc(device))
        return patient
