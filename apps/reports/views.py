"""
Reports views for analytics and dashboards.
"""
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from apps.core.models import get_db
from apps.devices.models import Device
from apps.orders.models import Order
from apps.vitals.models import Vital


def reports_dashboard(request):
    """Main reports dashboard with summary stats."""
    db = get_db()

    # Get date range
    days = int(request.GET.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    # Compliance stats
    compliance_stats = get_compliance_stats(db, start_date)

    # Connectivity stats
    connectivity_stats = get_connectivity_stats(db)

    # Order pipeline stats
    order_stats = get_order_pipeline_stats(db, start_date)

    context = {
        'days': days,
        'compliance_stats': compliance_stats,
        'connectivity_stats': connectivity_stats,
        'order_stats': order_stats,
    }

    return render(request, 'reports/dashboard.html', context)


def compliance_report(request):
    """Detailed compliance report - devices with readings."""
    db = get_db()
    days = int(request.GET.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get devices with their reading status
    devices = list(db.devices.find({'status': {'$ne': 'retired'}}))

    compliant = []
    non_compliant = []

    for device in devices:
        device['id'] = str(device['_id'])
        last_reading = device.get('last_reading_at')

        if last_reading and last_reading >= start_date:
            device['days_since_reading'] = (datetime.utcnow() - last_reading).days
            compliant.append(device)
        else:
            if last_reading:
                device['days_since_reading'] = (datetime.utcnow() - last_reading).days
            else:
                device['days_since_reading'] = None
            non_compliant.append(device)

    # Sort non-compliant by days since reading (most urgent first)
    non_compliant.sort(key=lambda d: d.get('days_since_reading') or 999, reverse=True)

    compliance_rate = (len(compliant) / len(devices) * 100) if devices else 0

    context = {
        'days': days,
        'compliant_devices': compliant,
        'non_compliant_devices': non_compliant,
        'total_devices': len(devices),
        'compliance_rate': round(compliance_rate, 1),
    }

    if request.htmx:
        return render(request, 'reports/partials/compliance_table.html', context)

    return render(request, 'reports/compliance.html', context)


def connectivity_report(request):
    """Connectivity report - offline device trends."""
    db = get_db()
    days = int(request.GET.get('days', 30))

    # Get current offline devices
    offline_devices = list(db.devices.find({
        'status': 'offline'
    }))

    for device in offline_devices:
        device['id'] = str(device['_id'])
        last_seen = device.get('last_reading_at')
        if last_seen:
            device['days_offline'] = (datetime.utcnow() - last_seen).days
        else:
            device['days_offline'] = None

    # Sort by days offline
    offline_devices.sort(key=lambda d: d.get('days_offline') or 999, reverse=True)

    # Get historical connectivity data (simulated - would need status history)
    connectivity_trend = get_connectivity_trend(db, days)

    context = {
        'days': days,
        'offline_devices': offline_devices,
        'total_offline': len(offline_devices),
        'connectivity_trend': connectivity_trend,
    }

    if request.htmx:
        return render(request, 'reports/partials/connectivity_table.html', context)

    return render(request, 'reports/connectivity.html', context)


def order_pipeline_report(request):
    """Order pipeline report - orders by status over time."""
    db = get_db()
    days = int(request.GET.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get orders created in date range
    orders = list(db.orders.find({
        'created_at': {'$gte': start_date}
    }))

    # Group by status
    status_counts = {}
    for order in orders:
        status = order.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    # Get orders by day for trend chart
    orders_by_day = get_orders_by_day(db, days)

    # Calculate metrics
    total_orders = len(orders)
    completed = status_counts.get('delivered', 0) + status_counts.get('completed', 0)
    pending = status_counts.get('pending', 0) + status_counts.get('processing', 0)
    shipped = status_counts.get('shipped', 0)

    context = {
        'days': days,
        'total_orders': total_orders,
        'status_counts': status_counts,
        'completed': completed,
        'pending': pending,
        'shipped': shipped,
        'orders_by_day': orders_by_day,
        'completion_rate': round(completed / total_orders * 100, 1) if total_orders else 0,
    }

    if request.htmx:
        return render(request, 'reports/partials/order_pipeline_table.html', context)

    return render(request, 'reports/order_pipeline.html', context)


def compliance_chart_data(request):
    """API endpoint for compliance chart data."""
    db = get_db()
    days = int(request.GET.get('days', 30))

    # Get daily compliance rates
    data = []
    for i in range(days, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Count devices with readings on or before this date
        total = db.devices.count_documents({'status': {'$ne': 'retired'}})
        with_readings = db.devices.count_documents({
            'status': {'$ne': 'retired'},
            'last_reading_at': {'$gte': date_start - timedelta(days=30)}
        })

        rate = (with_readings / total * 100) if total else 0
        data.append({
            'date': date_start.strftime('%Y-%m-%d'),
            'rate': round(rate, 1),
            'compliant': with_readings,
            'total': total
        })

    return JsonResponse({'data': data})


def connectivity_chart_data(request):
    """API endpoint for connectivity chart data."""
    db = get_db()
    days = int(request.GET.get('days', 30))

    # Get daily offline counts
    data = []
    for i in range(days, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')

        # For now, use current count (would need historical data)
        offline_count = db.devices.count_documents({'status': 'offline'})
        total = db.devices.count_documents({'status': {'$ne': 'retired'}})

        data.append({
            'date': date_str,
            'offline': offline_count,
            'online': total - offline_count,
            'total': total
        })

    return JsonResponse({'data': data})


def order_chart_data(request):
    """API endpoint for order pipeline chart data."""
    db = get_db()
    days = int(request.GET.get('days', 30))

    data = get_orders_by_day(db, days)
    return JsonResponse({'data': data})


# Helper functions

def get_compliance_stats(db, start_date):
    """Get compliance statistics."""
    total_devices = db.devices.count_documents({'status': {'$ne': 'retired'}})
    compliant = db.devices.count_documents({
        'status': {'$ne': 'retired'},
        'last_reading_at': {'$gte': start_date}
    })

    return {
        'total': total_devices,
        'compliant': compliant,
        'non_compliant': total_devices - compliant,
        'rate': round(compliant / total_devices * 100, 1) if total_devices else 0
    }


def get_connectivity_stats(db):
    """Get connectivity statistics."""
    total = db.devices.count_documents({'status': {'$ne': 'retired'}})
    online = db.devices.count_documents({'status': 'active'})
    offline = db.devices.count_documents({'status': 'offline'})

    return {
        'total': total,
        'online': online,
        'offline': offline,
        'online_rate': round(online / total * 100, 1) if total else 0
    }


def get_order_pipeline_stats(db, start_date):
    """Get order pipeline statistics."""
    pipeline = [
        {'$match': {'created_at': {'$gte': start_date}}},
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]
    result = list(db.orders.aggregate(pipeline))

    stats = {item['_id']: item['count'] for item in result}
    total = sum(stats.values())

    return {
        'total': total,
        'by_status': stats,
        'pending': stats.get('pending', 0),
        'processing': stats.get('processing', 0),
        'shipped': stats.get('shipped', 0),
        'delivered': stats.get('delivered', 0) + stats.get('completed', 0),
    }


def get_connectivity_trend(db, days):
    """Get connectivity trend data."""
    # Would need historical status tracking - for now return simulated data
    data = []
    for i in range(days, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'offline': db.devices.count_documents({'status': 'offline'}),
        })
    return data


def get_orders_by_day(db, days):
    """Get orders grouped by day."""
    data = []
    for i in range(days, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        count = db.orders.count_documents({
            'created_at': {'$gte': day_start, '$lt': day_end}
        })

        data.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'count': count
        })

    return data
