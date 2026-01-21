"""
Order document model for MongoDB.
"""
from datetime import datetime
import uuid
from apps.core.models import BaseDocument, serialize_doc


class Order(BaseDocument):
    """Order document model."""

    collection_name = 'orders'

    # Order status constants
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    @classmethod
    def generate_order_number(cls):
        """Generate a unique order number."""
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        unique_id = uuid.uuid4().hex[:6].upper()
        return f'ORD-{timestamp}-{unique_id}'

    @classmethod
    def create(cls, data: dict) -> str:
        """Create a new order."""
        document = {
            'order_number': data.get('order_number') or cls.generate_order_number(),
            'vendor_order_id': data.get('vendor_order_id'),
            'patient_id': data['patient_id'],
            'items': data.get('items', []),  # List of {device_type, quantity}
            'status': data.get('status', cls.STATUS_PENDING),
            'shipping_address': data.get('shipping_address', {}),
            'shipping_method': data.get('shipping_method', 'standard'),
            'tracking_number': data.get('tracking_number'),
            'tracking_url': data.get('tracking_url'),
            'shipped_at': data.get('shipped_at'),
            'delivered_at': data.get('delivered_at'),
            'notes': data.get('notes', ''),
            'status_history': [{
                'status': data.get('status', cls.STATUS_PENDING),
                'changed_at': datetime.utcnow(),
                'notes': 'Order created'
            }],
        }
        return cls.insert(document)

    @classmethod
    def find_by_order_number(cls, order_number: str):
        """Find order by order number."""
        return cls.find_one({'order_number': order_number})

    @classmethod
    def find_by_patient(cls, patient_id: str, limit: int = 50):
        """Find orders for a patient."""
        return cls.find(
            {'patient_id': patient_id},
            sort=[('created_at', -1)],
            limit=limit
        )

    @classmethod
    def search(cls, query: str = None, status: str = None,
               limit: int = 50, skip: int = 0):
        """Search orders with filters."""
        filter_query = {}

        if query:
            filter_query['$or'] = [
                {'order_number': {'$regex': query, '$options': 'i'}},
                {'vendor_order_id': {'$regex': query, '$options': 'i'}},
                {'tracking_number': {'$regex': query, '$options': 'i'}},
            ]

        if status:
            filter_query['status'] = status

        return cls.find(
            filter_query,
            sort=[('created_at', -1)],
            limit=limit,
            skip=skip
        )

    @classmethod
    def update_status(cls, order_id, new_status: str, notes: str = None,
                      tracking_number: str = None, tracking_url: str = None):
        """Update order status and add to history."""
        from bson import ObjectId
        if isinstance(order_id, str):
            order_id = ObjectId(order_id)

        status_entry = {
            'status': new_status,
            'changed_at': datetime.utcnow(),
            'notes': notes or f'Status changed to {new_status}'
        }

        update_data = {
            'status': new_status,
            'updated_at': datetime.utcnow()
        }

        if new_status == cls.STATUS_SHIPPED:
            update_data['shipped_at'] = datetime.utcnow()
            if tracking_number:
                update_data['tracking_number'] = tracking_number
            if tracking_url:
                update_data['tracking_url'] = tracking_url

        if new_status == cls.STATUS_DELIVERED:
            update_data['delivered_at'] = datetime.utcnow()

        cls.get_collection().update_one(
            {'_id': order_id},
            {
                '$set': update_data,
                '$push': {'status_history': status_entry}
            }
        )

    @classmethod
    def get_pending_orders(cls, limit: int = 50):
        """Get orders that need attention."""
        return cls.find(
            {'status': {'$in': [cls.STATUS_PENDING, cls.STATUS_PROCESSING]}},
            sort=[('created_at', 1)],
            limit=limit
        )

    @classmethod
    def count_by_status(cls):
        """Get order counts grouped by status."""
        pipeline = [
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
        ]
        result = list(cls.get_collection().aggregate(pipeline))
        return {item['_id']: item['count'] for item in result}

    @classmethod
    def get_recent(cls, limit: int = 10):
        """Get most recent orders."""
        return cls.find(sort=[('created_at', -1)], limit=limit)
