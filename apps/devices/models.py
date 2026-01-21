"""
Device document model for MongoDB.
"""
from datetime import datetime, timedelta
from apps.core.models import BaseDocument, serialize_doc


class Device(BaseDocument):
    """Device document model."""

    collection_name = 'devices'

    # Device status constants
    STATUS_INVENTORY = 'inventory'
    STATUS_ASSIGNED = 'assigned'
    STATUS_ACTIVE = 'active'
    STATUS_OFFLINE = 'offline'
    STATUS_RETURNED = 'returned'
    STATUS_LOST = 'lost'

    STATUS_CHOICES = [
        (STATUS_INVENTORY, 'In Inventory'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_OFFLINE, 'Offline'),
        (STATUS_RETURNED, 'Returned'),
        (STATUS_LOST, 'Lost'),
    ]

    @classmethod
    def create(cls, data: dict) -> str:
        """Create a new device."""
        document = {
            'serial_number': data['serial_number'],
            'hwi_device_id': data.get('hwi_device_id'),
            'device_type': data['device_type'],
            'device_model': data.get('device_model'),
            'manufacturer': data.get('manufacturer'),
            'status': data.get('status', cls.STATUS_INVENTORY),
            'patient_id': data.get('patient_id'),
            'order_id': data.get('order_id'),
            'last_reading_at': data.get('last_reading_at'),
            'assigned_at': data.get('assigned_at'),
            'status_history': [{
                'status': data.get('status', cls.STATUS_INVENTORY),
                'changed_at': datetime.utcnow(),
                'notes': 'Device created'
            }],
            'metadata': data.get('metadata', {}),
        }
        return cls.insert(document)

    @classmethod
    def find_by_serial(cls, serial_number: str):
        """Find device by serial number."""
        return cls.find_one({'serial_number': serial_number})

    @classmethod
    def search(cls, query: str = None, status: str = None, device_type: str = None,
               patient_id: str = None, limit: int = 50, skip: int = 0):
        """Search devices with filters."""
        filter_query = {}

        if query:
            filter_query['$or'] = [
                {'serial_number': {'$regex': query, '$options': 'i'}},
                {'hwi_device_id': {'$regex': query, '$options': 'i'}},
            ]

        if status:
            filter_query['status'] = status

        if device_type:
            filter_query['device_type'] = device_type

        if patient_id:
            filter_query['patient_id'] = patient_id

        return cls.find(
            filter_query,
            sort=[('updated_at', -1)],
            limit=limit,
            skip=skip
        )

    @classmethod
    def update_status(cls, device_id, new_status: str, notes: str = None):
        """Update device status and add to history."""
        from bson import ObjectId
        if isinstance(device_id, str):
            device_id = ObjectId(device_id)

        status_entry = {
            'status': new_status,
            'changed_at': datetime.utcnow(),
            'notes': notes or f'Status changed to {new_status}'
        }

        cls.get_collection().update_one(
            {'_id': device_id},
            {
                '$set': {
                    'status': new_status,
                    'updated_at': datetime.utcnow()
                },
                '$push': {'status_history': status_entry}
            }
        )

    @classmethod
    def assign_to_patient(cls, device_id, patient_id: str):
        """Assign device to a patient."""
        from bson import ObjectId
        if isinstance(device_id, str):
            device_id = ObjectId(device_id)

        cls.get_collection().update_one(
            {'_id': device_id},
            {
                '$set': {
                    'patient_id': patient_id,
                    'status': cls.STATUS_ASSIGNED,
                    'assigned_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                },
                '$push': {
                    'status_history': {
                        'status': cls.STATUS_ASSIGNED,
                        'changed_at': datetime.utcnow(),
                        'notes': f'Assigned to patient {patient_id}'
                    }
                }
            }
        )

        # Add device to patient's device list
        from apps.patients.models import Patient
        Patient.add_device(patient_id, str(device_id))

    @classmethod
    def unassign_from_patient(cls, device_id):
        """Remove device assignment from patient."""
        from bson import ObjectId
        if isinstance(device_id, str):
            device_id = ObjectId(device_id)

        device = cls.find_by_id(device_id)
        if device and device.get('patient_id'):
            # Remove from patient's device list
            from apps.patients.models import Patient
            Patient.remove_device(device['patient_id'], str(device_id))

        cls.get_collection().update_one(
            {'_id': device_id},
            {
                '$set': {
                    'patient_id': None,
                    'status': cls.STATUS_RETURNED,
                    'updated_at': datetime.utcnow()
                },
                '$push': {
                    'status_history': {
                        'status': cls.STATUS_RETURNED,
                        'changed_at': datetime.utcnow(),
                        'notes': 'Device unassigned from patient'
                    }
                }
            }
        )

    @classmethod
    def record_reading(cls, device_id, reading_time: datetime = None):
        """Record that a reading was received from this device."""
        from bson import ObjectId
        if isinstance(device_id, str):
            device_id = ObjectId(device_id)

        reading_time = reading_time or datetime.utcnow()

        cls.get_collection().update_one(
            {'_id': device_id},
            {
                '$set': {
                    'last_reading_at': reading_time,
                    'status': cls.STATUS_ACTIVE,
                    'updated_at': datetime.utcnow()
                }
            }
        )

    @classmethod
    def get_offline_devices(cls, threshold_days: int = 3):
        """Get devices that haven't reported in threshold_days."""
        threshold = datetime.utcnow() - timedelta(days=threshold_days)
        return cls.find({
            'status': {'$in': [cls.STATUS_ACTIVE, cls.STATUS_ASSIGNED]},
            'patient_id': {'$ne': None},
            '$or': [
                {'last_reading_at': {'$lt': threshold}},
                {'last_reading_at': None}
            ]
        })

    @classmethod
    def count_by_status(cls):
        """Get device counts grouped by status."""
        pipeline = [
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
        ]
        result = list(cls.get_collection().aggregate(pipeline))
        return {item['_id']: item['count'] for item in result}
