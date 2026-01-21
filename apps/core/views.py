"""Core views for CareAtlas Ops Dashboard."""
from django.http import HttpResponse


def health_check(request):
    """Health check endpoint for Railway deployment.

    This endpoint bypasses authentication and returns a 200 OK response
    to satisfy Railway's healthcheck requirements.
    """
    return HttpResponse("OK", status=200)
