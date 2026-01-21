"""
Ticket document model for MongoDB.
"""
from datetime import datetime
from apps.core.models import BaseDocument, serialize_doc


class Ticket(BaseDocument):
    """Ticket document model for support/issue tracking."""

    collection_name = 'tickets'

    # Ticket status constants
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]

    # Priority constants
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]

    # Category constants
    CATEGORY_DEVICE = 'device'
    CATEGORY_ORDER = 'order'
    CATEGORY_PATIENT = 'patient'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_DEVICE, 'Device Issue'),
        (CATEGORY_ORDER, 'Order Issue'),
        (CATEGORY_PATIENT, 'Patient Support'),
        (CATEGORY_OTHER, 'Other'),
    ]

    @classmethod
    def create(cls, data: dict) -> str:
        """Create a new ticket."""
        # Generate ticket number
        ticket_number = cls.generate_ticket_number()

        document = {
            'ticket_number': ticket_number,
            'title': data['title'],
            'description': data.get('description', ''),
            'status': data.get('status', cls.STATUS_OPEN),
            'priority': data.get('priority', cls.PRIORITY_MEDIUM),
            'category': data.get('category', cls.CATEGORY_OTHER),
            'patient_id': data.get('patient_id'),
            'device_id': data.get('device_id'),
            'order_id': data.get('order_id'),
            'assigned_to': data.get('assigned_to'),
            'messages': [{
                'content': data.get('description', ''),
                'author': 'System',
                'created_at': datetime.utcnow(),
                'is_internal': False,
            }] if data.get('description') else [],
            'sla_due_at': cls.calculate_sla(data.get('priority', cls.PRIORITY_MEDIUM)),
            'resolved_at': None,
            'closed_at': None,
        }
        return cls.insert(document)

    @classmethod
    def generate_ticket_number(cls) -> str:
        """Generate a unique ticket number."""
        from random import randint
        year = datetime.utcnow().strftime('%y')
        random_num = randint(10000, 99999)
        return f'TKT-{year}-{random_num}'

    @classmethod
    def calculate_sla(cls, priority: str) -> datetime:
        """Calculate SLA due date based on priority."""
        from datetime import timedelta

        sla_hours = {
            cls.PRIORITY_URGENT: 4,
            cls.PRIORITY_HIGH: 24,
            cls.PRIORITY_MEDIUM: 48,
            cls.PRIORITY_LOW: 72,
        }
        hours = sla_hours.get(priority, 48)
        return datetime.utcnow() + timedelta(hours=hours)

    @classmethod
    def find_by_number(cls, ticket_number: str):
        """Find ticket by ticket number."""
        return cls.find_one({'ticket_number': ticket_number})

    @classmethod
    def search(cls, query: str = None, status: str = None, priority: str = None,
               category: str = None, limit: int = 50, skip: int = 0):
        """Search tickets with filters."""
        filter_query = {}

        if query:
            filter_query['$or'] = [
                {'ticket_number': {'$regex': query, '$options': 'i'}},
                {'title': {'$regex': query, '$options': 'i'}},
            ]

        if status:
            filter_query['status'] = status

        if priority:
            filter_query['priority'] = priority

        if category:
            filter_query['category'] = category

        return cls.find(
            filter_query,
            sort=[('created_at', -1)],
            limit=limit,
            skip=skip
        )

    @classmethod
    def add_message(cls, ticket_id, content: str, author: str = 'Support', is_internal: bool = False):
        """Add a message to the ticket."""
        from bson import ObjectId
        if isinstance(ticket_id, str):
            ticket_id = ObjectId(ticket_id)

        message = {
            'content': content,
            'author': author,
            'created_at': datetime.utcnow(),
            'is_internal': is_internal,
        }

        cls.get_collection().update_one(
            {'_id': ticket_id},
            {
                '$push': {'messages': message},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )

    @classmethod
    def update_status(cls, ticket_id, new_status: str, notes: str = None):
        """Update ticket status."""
        from bson import ObjectId
        if isinstance(ticket_id, str):
            ticket_id = ObjectId(ticket_id)

        update = {
            'status': new_status,
            'updated_at': datetime.utcnow()
        }

        if new_status == cls.STATUS_RESOLVED:
            update['resolved_at'] = datetime.utcnow()
        elif new_status == cls.STATUS_CLOSED:
            update['closed_at'] = datetime.utcnow()

        cls.get_collection().update_one(
            {'_id': ticket_id},
            {'$set': update}
        )

        if notes:
            cls.add_message(ticket_id, notes, 'System', is_internal=True)

    @classmethod
    def count_by_status(cls):
        """Get ticket counts grouped by status."""
        pipeline = [
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
        ]
        result = list(cls.get_collection().aggregate(pipeline))
        return {item['_id']: item['count'] for item in result}

    @classmethod
    def get_open_tickets(cls, limit: int = 50):
        """Get all open and in-progress tickets."""
        return cls.find(
            {'status': {'$in': [cls.STATUS_OPEN, cls.STATUS_IN_PROGRESS]}},
            sort=[('priority', 1), ('created_at', 1)],
            limit=limit
        )

    @classmethod
    def get_overdue_tickets(cls):
        """Get tickets that are past their SLA."""
        return cls.find({
            'status': {'$in': [cls.STATUS_OPEN, cls.STATUS_IN_PROGRESS]},
            'sla_due_at': {'$lt': datetime.utcnow()}
        })
