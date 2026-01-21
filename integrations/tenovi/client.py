"""
Tenovi API client with sandbox mode support.
"""
import logging
import requests
from django.conf import settings
from .sandbox import SandboxGenerator

logger = logging.getLogger(__name__)


class TenoviClient:
    """
    Tenovi API client.

    When TENOVI_SANDBOX_MODE is True, returns fake responses instead of
    making real API calls.
    """

    def __init__(self):
        self.sandbox = settings.TENOVI_SANDBOX_MODE
        self.api_key = settings.TENOVI_API_KEY
        self.client_domain = settings.TENOVI_CLIENT_DOMAIN
        self.base_url = settings.TENOVI_API_BASE_URL

    def _headers(self) -> dict:
        """Get API request headers."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-Client-Domain': self.client_domain,
        }

    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make an API request."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Tenovi API error: {e}")
            raise TenoviAPIError(str(e))

    def create_device_order(self, patient_id: str, items: list,
                            shipping_address: dict, order_reference: str = None) -> dict:
        """
        Create a device order.

        Args:
            patient_id: Internal patient ID
            items: List of {device_type, quantity}
            shipping_address: Shipping address dict
            order_reference: Optional internal order reference

        Returns:
            Order response with order_id
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Creating order for patient {patient_id}")
            return SandboxGenerator.fake_order_response(
                patient_id=patient_id,
                items=items,
                order_reference=order_reference
            )

        data = {
            'patient_id': patient_id,
            'items': items,
            'shipping_address': shipping_address,
            'order_reference': order_reference,
        }

        return self._request('POST', 'orders', data)

    def get_order_status(self, order_id: str) -> dict:
        """
        Get order status.

        Args:
            order_id: Tenovi order ID

        Returns:
            Order status response
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Getting status for order {order_id}")
            return SandboxGenerator.fake_order_status(order_id)

        return self._request('GET', f'orders/{order_id}')

    def cancel_order(self, order_id: str, reason: str = None) -> dict:
        """
        Cancel an order.

        Args:
            order_id: Tenovi order ID
            reason: Cancellation reason

        Returns:
            Cancellation response
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Cancelling order {order_id}")
            return {'order_id': order_id, 'status': 'cancelled'}

        data = {'reason': reason} if reason else {}
        return self._request('POST', f'orders/{order_id}/cancel', data)

    def register_device(self, serial_number: str, device_type: str,
                        patient_id: str) -> dict:
        """
        Register a device with Tenovi.

        Args:
            serial_number: Device serial number
            device_type: Device type
            patient_id: Patient ID to associate

        Returns:
            Device registration response
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Registering device {serial_number}")
            return SandboxGenerator.fake_device_registration(
                serial_number=serial_number,
                device_type=device_type,
                patient_id=patient_id
            )

        data = {
            'serial_number': serial_number,
            'device_type': device_type,
            'patient_id': patient_id,
        }

        return self._request('POST', 'devices/register', data)

    def unregister_device(self, device_id: str) -> dict:
        """
        Unregister a device.

        Args:
            device_id: Tenovi device ID

        Returns:
            Unregistration response
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Unregistering device {device_id}")
            return {'device_id': device_id, 'status': 'unregistered'}

        return self._request('DELETE', f'devices/{device_id}')

    def get_patient_devices(self, patient_id: str) -> list:
        """
        Get all devices for a patient.

        Args:
            patient_id: Patient ID

        Returns:
            List of devices
        """
        if self.sandbox:
            logger.info(f"[SANDBOX] Getting devices for patient {patient_id}")
            return []

        response = self._request('GET', f'patients/{patient_id}/devices')
        return response.get('devices', [])


class TenoviAPIError(Exception):
    """Exception for Tenovi API errors."""
    pass
