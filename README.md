# CareAtlas Ops Dashboard

A healthcare operations dashboard for remote patient monitoring (RPM) programs. Built with Django, HTMX, Alpine.js, and DaisyUI.

![Dashboard Preview](https://img.shields.io/badge/Django-4.2-green) ![HTMX](https://img.shields.io/badge/HTMX-2.0-blue) ![DaisyUI](https://img.shields.io/badge/DaisyUI-4.7-purple)

## Features

- **Patient Management** - Track active patients, view details, and manage patient records
- **Device Monitoring** - Monitor RPM devices with real-time connectivity alerts
- **Order Processing** - Multi-step order workflow for device fulfillment
- **Support Tickets** - Built-in ticketing system for patient support
- **Vitals Tracking** - View patient vital signs with charts and history
- **Reports & Analytics** - Compliance, connectivity, and order pipeline reports

## Tech Stack

- **Backend:** Django 4.2, Python 3.9+
- **Frontend:** HTMX, Alpine.js, TailwindCSS, DaisyUI
- **Database:** MongoDB (via PyMongo) / SQLite for sessions
- **UI:** Responsive design with mobile-first approach

## Quick Start

### Prerequisites

- Python 3.9 or higher
- MongoDB (local or Atlas connection string)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/traviso92/careatlas-ops-dashboard.git
   cd careatlas-ops-dashboard
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your MongoDB connection string
   ```

5. **Seed the database with sample data**
   ```bash
   python manage.py seed_sandbox
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Open your browser**
   ```
   http://localhost:8000
   ```

## Project Structure

```
ops-dashboard/
├── apps/
│   ├── core/          # Shared models, middleware, template tags
│   ├── dashboard/     # Main dashboard views and stats
│   ├── patients/      # Patient management
│   ├── devices/       # Device monitoring
│   ├── orders/        # Order processing workflow
│   ├── tickets/       # Support ticket system
│   ├── vitals/        # Vital signs tracking
│   └── reports/       # Analytics and reports
├── config/            # Django settings and URL config
├── integrations/      # Third-party integrations (Tenovi)
├── sandbox/           # Sample data for development
├── static/            # CSS and static assets
└── templates/         # HTML templates
```

## Sandbox Mode

The application runs in sandbox mode by default, using mock data for development and demonstration. This includes:

- 50 sample patients
- 30 RPM devices (blood pressure monitors, weight scales, pulse oximeters)
- Sample orders in various states
- Simulated vital sign readings

## Screenshots

### Dashboard
The main dashboard shows key metrics, recent orders, and connectivity alerts at a glance.

### Patient Management
View and manage patient records with search, filtering, and detailed patient profiles.

### Device Monitoring
Track device status with offline alerts and connectivity reports.

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `careatlas_ops` |
| `DEBUG` | Debug mode | `True` |
| `SECRET_KEY` | Django secret key | (generate one) |

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
The project follows PEP 8 guidelines for Python code.

## License

MIT License - feel free to use this for your own projects.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Built with Django + HTMX + DaisyUI
