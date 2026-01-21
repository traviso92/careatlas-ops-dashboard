"""
Custom middleware for HTMX support.
"""
from django.shortcuts import render


class HTMXMiddleware:
    """Middleware for enhanced HTMX support."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        """Add HTMX-specific context."""
        if hasattr(response, 'context_data'):
            response.context_data['is_htmx'] = getattr(request, 'htmx', False)
        return response


class ToastMiddleware:
    """Middleware to handle toast notifications via HTMX."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add HX-Trigger header for toast notifications if set
        if hasattr(request, '_toast_message'):
            import json
            response['HX-Trigger'] = json.dumps({
                'showToast': {
                    'message': request._toast_message,
                    'type': getattr(request, '_toast_type', 'info')
                }
            })

        return response


def add_toast(request, message: str, toast_type: str = 'info'):
    """Helper to add a toast notification to the response."""
    request._toast_message = message
    request._toast_type = toast_type
