"""
Custom middleware for HTMX support and authentication.
"""
from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse
import re


class LoginRequiredMiddleware:
    """Middleware to require login for all pages except auth URLs."""

    EXEMPT_URLS = [
        r'^/accounts/',
        r'^/admin/',
        r'^/static/',
        r'^/favicon\.ico$',
        r'^/health/$',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [re.compile(url) for url in self.EXEMPT_URLS]

    def __call__(self, request):
        path = request.path_info

        # Check if path is exempt
        if any(pattern.match(path) for pattern in self.exempt_urls):
            return self.get_response(request)

        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)

        # Check domain restriction
        if hasattr(settings, 'ALLOWED_EMAIL_DOMAINS') and settings.ALLOWED_EMAIL_DOMAINS:
            email = getattr(request.user, 'email', '')
            if email:
                domain = email.split('@')[-1].lower()
                allowed = [d.strip().lower() for d in settings.ALLOWED_EMAIL_DOMAINS]
                if domain not in allowed:
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('/accounts/login/?error=domain')

        return self.get_response(request)


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
