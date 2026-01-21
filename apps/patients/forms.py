"""
Patient forms.
"""
from django import forms


class PatientForm(forms.Form):
    """Form for creating/editing patients."""

    mrn = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Medical Record Number'
        })
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Last Name'
        })
    )
    dob = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'input input-bordered w-full',
            'type': 'date'
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Email'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Phone'
        })
    )
    street = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Street Address'
        })
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'City'
        })
    )
    state = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'State'
        })
    )
    zip_code = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'ZIP Code'
        })
    )
    program = forms.ChoiceField(
        choices=[
            ('RPM', 'Remote Patient Monitoring'),
            ('CCM', 'Chronic Care Management'),
            ('RTM', 'Remote Therapeutic Monitoring'),
        ],
        widget=forms.Select(attrs={
            'class': 'select select-bordered w-full'
        })
    )
    conditions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full',
            'placeholder': 'Conditions (comma-separated)',
            'rows': 2
        })
    )


class PatientSearchForm(forms.Form):
    """Form for searching patients."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Search by MRN, name, or email...',
            'hx-get': '/patients/',
            'hx-trigger': 'keyup changed delay:300ms',
            'hx-target': '#patient-list',
            'hx-swap': 'innerHTML',
            'hx-push-url': 'true'
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Statuses'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={
            'class': 'select select-bordered',
            'hx-get': '/patients/',
            'hx-trigger': 'change',
            'hx-target': '#patient-list',
            'hx-swap': 'innerHTML',
            'hx-include': '[name="q"]'
        })
    )
    program = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Programs'),
            ('RPM', 'RPM'),
            ('CCM', 'CCM'),
            ('RTM', 'RTM'),
        ],
        widget=forms.Select(attrs={
            'class': 'select select-bordered',
            'hx-get': '/patients/',
            'hx-trigger': 'change',
            'hx-target': '#patient-list',
            'hx-swap': 'innerHTML',
            'hx-include': '[name="q"], [name="status"]'
        })
    )
