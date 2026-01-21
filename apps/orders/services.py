"""
Order services for business logic.
"""
from datetime import datetime
from .models import Order
from apps.patients.models import Patient
from integrations.tenovi.client import TenoviClient


class OrderService:
    """Service class for order operations."""

    def __init__(self):
        self.tenovi = TenoviClient()

    def create_order(self, patient_id: str, items: list, shipping_address: dict = None,
                     notes: str = None):
        """
        Create a new device order.

        Args:
            patient_id: The patient ID
            items: List of dicts with device_type and quantity
            shipping_address: Optional override for shipping address
            notes: Optional order notes

        Returns:
            The created order ID
        """
        # Get patient info
        patient = Patient.find_by_id(patient_id)
        if not patient:
            raise ValueError('Patient not found')

        # Use patient address if not provided
        if not shipping_address:
            shipping_address = patient.get('address', {})
            shipping_address['name'] = f"{patient.get('first_name', '')} {patient.get('last_name', '')}"

        # Create order in our system
        order_data = {
            'patient_id': patient_id,
            'items': items,
            'shipping_address': shipping_address,
            'notes': notes or '',
            'status': Order.STATUS_PENDING,
        }

        order_id = Order.create(order_data)
        order = Order.find_by_id(order_id)

        # Submit to Tenovi (sandbox or real)
        tenovi_response = self.tenovi.create_device_order(
            patient_id=patient_id,
            items=items,
            shipping_address=shipping_address,
            order_reference=order['order_number']
        )

        # Update order with vendor order ID
        if tenovi_response.get('order_id'):
            Order.update(order_id, {
                'vendor_order_id': tenovi_response['order_id'],
                'status': Order.STATUS_PROCESSING
            })
            Order.update_status(
                order_id,
                Order.STATUS_PROCESSING,
                notes=f"Submitted to Tenovi: {tenovi_response['order_id']}"
            )

        return str(order_id)

    def cancel_order(self, order_id: str, reason: str = None):
        """
        Cancel an order.
        """
        order = Order.find_by_id(order_id)
        if not order:
            raise ValueError('Order not found')

        if order['status'] in [Order.STATUS_SHIPPED, Order.STATUS_DELIVERED]:
            raise ValueError('Cannot cancel shipped or delivered orders')

        # TODO: Call Tenovi to cancel if not in sandbox mode

        Order.update_status(
            order_id,
            Order.STATUS_CANCELLED,
            notes=reason or 'Order cancelled'
        )

        return True

    def process_fulfillment_update(self, vendor_order_id: str, status: str,
                                    tracking_number: str = None,
                                    tracking_url: str = None):
        """
        Process a fulfillment status update from Tenovi webhook.
        """
        order = Order.find_one({'vendor_order_id': vendor_order_id})
        if not order:
            raise ValueError(f'Order not found for vendor_order_id: {vendor_order_id}')

        # Map Tenovi status to our status
        status_map = {
            'processing': Order.STATUS_PROCESSING,
            'shipped': Order.STATUS_SHIPPED,
            'delivered': Order.STATUS_DELIVERED,
            'cancelled': Order.STATUS_CANCELLED,
        }

        new_status = status_map.get(status.lower())
        if not new_status:
            raise ValueError(f'Unknown status: {status}')

        Order.update_status(
            order['_id'],
            new_status,
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            notes=f'Fulfillment update from Tenovi: {status}'
        )

        # If delivered, create device records and assign to patient
        if new_status == Order.STATUS_DELIVERED:
            self._process_delivery(order)

        return True

    def _process_delivery(self, order: dict):
        """
        Process a delivered order - create device records.
        """
        from apps.devices.models import Device

        for item in order.get('items', []):
            # In sandbox mode, we generate fake serial numbers
            # In production, these would come from the Tenovi webhook
            for i in range(item.get('quantity', 1)):
                serial = f"SIM-{order['order_number']}-{item['device_type'][:3].upper()}-{i+1}"

                device_id = Device.create({
                    'serial_number': serial,
                    'device_type': item['device_type'],
                    'status': Device.STATUS_ASSIGNED,
                    'patient_id': order['patient_id'],
                    'order_id': str(order['_id']),
                    'assigned_at': datetime.utcnow(),
                })

                # Add device to patient
                Patient.add_device(order['patient_id'], str(device_id))

    def get_order_stats(self):
        """
        Get order statistics.
        """
        status_counts = Order.count_by_status()
        pending_count = status_counts.get(Order.STATUS_PENDING, 0) + \
                       status_counts.get(Order.STATUS_PROCESSING, 0)

        return {
            'total': sum(status_counts.values()),
            'by_status': status_counts,
            'pending': pending_count,
        }
