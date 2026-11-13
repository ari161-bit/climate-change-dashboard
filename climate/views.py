from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import analytics
from .models import AlertThreshold, Feedback

ADMIN_GROUP = 'Administrators'
ANALYST_GROUP = 'Analysts'


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists())


def role_of(user):
    if is_admin(user):
        return 'Administrator'
    if user.groups.filter(name=ANALYST_GROUP).exists():
        return 'Analyst'
    return 'Viewer'


def admin_required(view):
    @login_required(login_url='climate:login')
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            messages.error(request, 'That page is restricted to administrators.')
            return redirect('climate:dashboard')
        return view(request, *args, **kwargs)
    return wrapped


def current_thresholds():
    existing = {t.key: t.value for t in AlertThreshold.objects.all()}
    return {key: existing.get(key, default) for key, _, default, _, _ in analytics.DEFAULT_THRESHOLDS}


def ensure_thresholds():
    for key, label, value, unit, desc in analytics.DEFAULT_THRESHOLDS:
        AlertThreshold.objects.get_or_create(key=key, defaults={
            'label': label, 'value': value, 'unit': unit, 'description': desc})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('climate:dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user is not None:
            login(request, user)
            target = request.POST.get('next', '')
            if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
                return redirect(target)
            return redirect('climate:dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'climate/login.html', {'next': request.GET.get('next', '')})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('climate:login')


@login_required(login_url='climate:login')
def dashboard(request):
    return render(request, 'climate/dashboard.html', {
        'role': role_of(request.user),
        'is_admin': is_admin(request.user),
        'maps_key': '',
    })


@login_required(login_url='climate:login')
def dashboard_data(request):
    def as_int(name):
        try:
            return int(request.GET.get(name, ''))
        except ValueError:
            return None
    return JsonResponse(analytics.dashboard_data(as_int('start'), as_int('end'), current_thresholds()))


@login_required(login_url='climate:login')
def feedback(request):
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()[:120]
        message = request.POST.get('message', '').strip()[:2000]
        category = request.POST.get('category', 'question')
        if category not in dict(Feedback.CATEGORIES):
            category = 'question'
        if not subject or not message:
            messages.error(request, 'Please fill in both a subject and a message.')
        else:
            Feedback.objects.create(user=request.user, category=category, subject=subject, message=message)
            messages.success(request, 'Thanks - your message was sent to the agency team.')
            return redirect('climate:feedback')
    mine = Feedback.objects.filter(user=request.user)
    return render(request, 'climate/feedback.html', {
        'categories': Feedback.CATEGORIES,
        'items': mine,
        'role': role_of(request.user),
        'is_admin': is_admin(request.user),
    })


@admin_required
def admin_panel(request):
    ensure_thresholds()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'thresholds':
            for threshold in AlertThreshold.objects.all():
                raw = request.POST.get(f'th_{threshold.key}', '')
                try:
                    value = float(raw)
                except ValueError:
                    messages.error(request, f'"{raw}" is not a valid number for {threshold.label}.')
                    continue
                if value <= 0:
                    messages.error(request, f'{threshold.label} must be greater than zero.')
                    continue
                threshold.value = value
                threshold.save()
            messages.success(request, 'Alert thresholds updated.')
        elif action == 'respond':
            try:
                item = Feedback.objects.get(pk=int(request.POST.get('feedback_id', '')))
            except (ValueError, Feedback.DoesNotExist):
                messages.error(request, 'That message no longer exists.')
            else:
                item.response = request.POST.get('response', '').strip()[:2000]
                item.status = 'resolved' if request.POST.get('resolve') else 'open'
                item.save()
                messages.success(request, 'Response saved.')
        return redirect('climate:admin_panel')

    data = analytics.dashboard_data(thresholds=current_thresholds())
    return render(request, 'climate/admin_panel.html', {
        'thresholds': AlertThreshold.objects.all(),
        'alerts': data['alerts'],
        'feedback_items': Feedback.objects.select_related('user'),
        'role': role_of(request.user),
        'is_admin': True,
    })
