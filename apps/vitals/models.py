"""
Vital document model for MongoDB (time-series data).
"""
from datetime import datetime, timedelta
from apps.core.models import BaseDocument, get_db


class Vital(BaseDocument):
    """Vital reading document model."""

    collection_name = 'vitals'

    @classmethod
    def setup_indexes(cls):
        """Create indexes for time-series queries."""
        collection = cls.get_collection()
        collection.create_index([('patient_id', 1), ('timestamp', -1)])
        collection.create_index([('device_id', 1), ('timestamp', -1)])
        collection.create_index('timestamp', expireAfterSeconds=365*24*60*60)  # TTL: 1 year

    @classmethod
    def create(cls, data: dict) -> str:
        """Create a new vital reading."""
        document = {
            'patient_id': data['patient_id'],
            'device_id': data.get('device_id'),
            'device_type': data.get('device_type'),
            'timestamp': data.get('timestamp', datetime.utcnow()),
            'readings': data.get('readings', {}),
            'metadata': data.get('metadata', {}),
            'source': data.get('source', 'device'),
        }
        return cls.insert(document)

    @classmethod
    def get_recent(cls, patient_id: str, limit: int = 50, device_type: str = None):
        """Get recent vitals for a patient."""
        query = {'patient_id': patient_id}
        if device_type:
            query['device_type'] = device_type

        return cls.find(
            query,
            sort=[('timestamp', -1)],
            limit=limit
        )

    @classmethod
    def find_by_device(cls, device_id: str, limit: int = 50):
        """Get vitals from a specific device."""
        return cls.find(
            {'device_id': device_id},
            sort=[('timestamp', -1)],
            limit=limit
        )

    @classmethod
    def get_time_range(cls, patient_id: str, start: datetime, end: datetime,
                       device_type: str = None):
        """Get vitals within a time range."""
        query = {
            'patient_id': patient_id,
            'timestamp': {'$gte': start, '$lte': end}
        }
        if device_type:
            query['device_type'] = device_type

        return cls.find(query, sort=[('timestamp', 1)])

    @classmethod
    def get_daily_aggregates(cls, patient_id: str, device_type: str, days: int = 30):
        """Get daily aggregated readings."""
        start_date = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {
                '$match': {
                    'patient_id': patient_id,
                    'device_type': device_type,
                    'timestamp': {'$gte': start_date}
                }
            },
            {
                '$group': {
                    '_id': {
                        'year': {'$year': '$timestamp'},
                        'month': {'$month': '$timestamp'},
                        'day': {'$dayOfMonth': '$timestamp'}
                    },
                    'readings': {'$push': '$readings'},
                    'count': {'$sum': 1}
                }
            },
            {'$sort': {'_id': 1}}
        ]

        return list(cls.get_collection().aggregate(pipeline))

    @classmethod
    def get_latest_by_type(cls, patient_id: str):
        """Get the most recent vital of each type for a patient."""
        pipeline = [
            {'$match': {'patient_id': patient_id}},
            {'$sort': {'timestamp': -1}},
            {
                '$group': {
                    '_id': '$device_type',
                    'latest': {'$first': '$$ROOT'}
                }
            }
        ]

        results = list(cls.get_collection().aggregate(pipeline))
        return {r['_id']: r['latest'] for r in results}


class VitalReading:
    """Helper class for parsing vital readings."""

    BLOOD_PRESSURE = 'blood_pressure'
    WEIGHT = 'weight'
    BLOOD_GLUCOSE = 'blood_glucose'
    PULSE_OXIMETER = 'pulse_oximeter'
    THERMOMETER = 'thermometer'

    @staticmethod
    def parse_blood_pressure(readings: dict) -> dict:
        """Parse blood pressure reading."""
        return {
            'systolic': readings.get('systolic'),
            'diastolic': readings.get('diastolic'),
            'pulse': readings.get('pulse'),
            'irregular': readings.get('irregular', False),
        }

    @staticmethod
    def parse_weight(readings: dict) -> dict:
        """Parse weight reading."""
        return {
            'weight_lbs': readings.get('weight_lbs'),
            'weight_kg': readings.get('weight_kg'),
            'bmi': readings.get('bmi'),
        }

    @staticmethod
    def parse_blood_glucose(readings: dict) -> dict:
        """Parse blood glucose reading."""
        return {
            'glucose_mg_dl': readings.get('glucose_mg_dl'),
            'meal_context': readings.get('meal_context'),  # before_meal, after_meal, fasting
        }

    @staticmethod
    def parse_pulse_oximeter(readings: dict) -> dict:
        """Parse pulse oximeter reading."""
        return {
            'spo2': readings.get('spo2'),
            'pulse': readings.get('pulse'),
            'perfusion_index': readings.get('perfusion_index'),
        }

    @staticmethod
    def parse_temperature(readings: dict) -> dict:
        """Parse temperature reading."""
        return {
            'temperature_f': readings.get('temperature_f'),
            'temperature_c': readings.get('temperature_c'),
            'measurement_site': readings.get('measurement_site'),  # oral, ear, forehead
        }
