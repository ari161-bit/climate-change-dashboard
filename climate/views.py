import io
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from functools import wraps

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from . import analytics, lake, live as live_feed, ml, monitor
from .models import AlertThreshold, AuditLog, CustomDataset, Feedback, ModelRun
from .roles import ADMIN_GROUP, ANALYST_GROUP, is_admin, role_of

LOGIN = 'climate:login'
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', ''))[:45]


def audit(request, action, detail=''):
    user = request.user.username if request.user.is_authenticated else ''
    AuditLog.objects.create(user=user, action=action, detail=detail[:300], ip=client_ip(request))


def admin_required(view):
    @wraps(view)
    @login_required(login_url=LOGIN)
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
        AlertThreshold.objects.get_or_create(key=key, defaults={'label': label, 'value': value, 'unit': unit, 'description': desc})


# ---------------------------------------------------------------- authentication
def csrf_failure(request, reason=''):
    """A stale form (for example, a second tab that has since signed in) should not strand the user on a bare 403."""
    messages.error(request, 'Your form had expired, so nothing was submitted. Please try again.')
    return redirect('climate:login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('climate:dashboard')
    username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        user = authenticate(request, username=username, password=request.POST.get('password', ''))
        if user is not None:
            login(request, user)
            audit(request, 'login')
            target = request.POST.get('next', '')
            if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(target)
            return redirect('climate:dashboard')
        AuditLog.objects.create(user=username[:150], action='login_failed', ip=client_ip(request))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'climate/login.html', {'next': request.GET.get('next', ''), 'username': username})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('climate:dashboard')
    form = {'username': '', 'email': ''}
    if request.method == 'POST':
        form = {'username': request.POST.get('username', '').strip(), 'email': request.POST.get('email', '').strip()}
        password, confirm = request.POST.get('password', ''), request.POST.get('confirm', '')
        error = None
        if not re.fullmatch(r'[\w.@+-]{3,40}', form['username']):
            error = 'Usernames must be 3-40 characters: letters, digits and . @ + - _'
        elif User.objects.filter(username__iexact=form['username']).exists():
            error = 'That username is taken.'
        elif password != confirm:
            error = 'The two passwords do not match.'
        else:
            try:
                validate_password(password, User(username=form['username'], email=form['email']))
            except ValidationError as exc:
                error = ' '.join(exc.messages)
        if error:
            messages.error(request, error)
        else:
            user = User.objects.create_user(form['username'], form['email'], password)
            user.groups.add(Group.objects.get_or_create(name=ANALYST_GROUP)[0])
            login(request, user)
            audit(request, 'signup', 'self-registered as Analyst')
            messages.success(request, 'Welcome aboard. Your account has the Analyst role.')
            return redirect('climate:dashboard')
    return render(request, 'climate/signup.html', {'form': form})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit(request, 'logout')
    logout(request)
    return redirect('climate:login')


# ---------------------------------------------------------------- dashboard
@login_required(login_url=LOGIN)
def dashboard(request):
    return render(request, 'climate/dashboard.html')


@login_required(login_url=LOGIN)
def dashboard_data(request):
    def as_int(name):
        try:
            return int(request.GET.get(name, ''))
        except ValueError:
            return None
    return JsonResponse(analytics.dashboard_data(as_int('start'), as_int('end'), current_thresholds()))


# ---------------------------------------------------------------- data explorer
def visible_custom(user):
    qs = CustomDataset.objects.all()
    return qs if is_admin(user) else qs.filter(visibility='analysts')


@login_required(login_url=LOGIN)
def explorer(request):
    custom = visible_custom(request.user)
    return render(request, 'climate/explorer.html', {
        'catalogue': analytics.catalogue(), 'custom': custom,
        'lake_kb': round(lake.lake_size_bytes() / 1024),
    })


@login_required(login_url=LOGIN)
def explorer_data(request, name):
    if name.startswith('custom:'):
        try:
            ds = visible_custom(request.user).get(slug=name[7:])
        except CustomDataset.DoesNotExist:
            raise Http404
        pts = ds.points
        values = [p[1] for p in pts]
        return JsonResponse({'name': name, 'title': ds.title, 'unit': ds.unit, 'column': 'value', 'columns': ['value'], 'group_label': None,
                             'groups': [], 'group': None, 'kind': 'linear', 'points': pts,
                             'stats': {'count': len(values), 'min': min(values), 'max': max(values), 'mean': round(sum(values) / len(values), 3)}})
    if name not in lake.load_manifest():
        raise Http404
    return JsonResponse(analytics.dataset_preview(name, request.GET.get('column'), request.GET.get('group')))


@admin_required
def explorer_download(request, name):
    """Raw CSV export - administrators only (role-based data access)."""
    if name not in lake.load_manifest():
        raise Http404
    frame = lake.read_dataset(name)
    audit(request, 'download', name)
    response = HttpResponse(frame.to_csv(index=False), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{name}.csv"'
    return response


# ---------------------------------------------------------------- trend analyzer
@login_required(login_url=LOGIN)
def trends(request):
    return render(request, 'climate/trends.html', {'datasets': analytics.ANALYZER_DATASETS})


@login_required(login_url=LOGIN)
def trends_options(request):
    dataset = request.GET.get('dataset', '')
    if dataset not in analytics.ANALYZER_DATASETS:
        raise Http404
    return JsonResponse(analytics.analyzer_options(dataset, request.GET.get('indicator')))


@login_required(login_url=LOGIN)
def trends_data(request):
    dataset = request.GET.get('dataset', '')
    if dataset not in analytics.ANALYZER_DATASETS:
        raise Http404
    try:
        horizon = int(request.GET.get('horizon', 2035))
    except ValueError:
        horizon = 2035
    try:
        return JsonResponse(analytics.trend_analysis(dataset, request.GET.get('entity', ''), request.GET.get('indicator', ''), horizon,
                                                     request.GET.get('model', 'auto')))
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=422)


# ---------------------------------------------------------------- real-time + satellite
@login_required(login_url=LOGIN)
def live(request):
    return render(request, 'climate/live.html')


@login_required(login_url=LOGIN)
def live_data(request):
    return JsonResponse(live_feed.fetch_live(current_thresholds()))


@login_required(login_url=LOGIN)
def satellite(request):
    cities = [{'city': name, 'lat': lat, 'lon': lon} for name, (lat, lon) in live_feed.CITIES.items()]
    return render(request, 'climate/satellite.html', {'cities': cities})


# ---------------------------------------------------------------- models
@login_required(login_url=LOGIN)
def models_page(request):
    if request.method == 'POST':
        if not is_admin(request.user):
            messages.error(request, 'Only administrators can retrain models.')
            return redirect('climate:models')
        runs = ml.train_all(request.user.username)
        audit(request, 'retrain', f'{len(runs)} models, data through {runs[0].data_through}')
        messages.success(request, f'Retrained {len(runs)} models on data through {runs[0].data_through}.')
        return redirect('climate:models')
    annual = ml.annual_temperature()['global_anomaly']
    trend = ml.trend_model(annual)
    regimes = ml.regime_model()
    corr = ml.correlation_model()
    anomalies = ml.anomaly_model(annual)
    return render(request, 'climate/models.html', {
        'runs': ModelRun.objects.all()[:12],
        'scores': {ml.MODEL_LABELS[k]: v for k, v in trend['scores'].items()},
        'best': ml.MODEL_LABELS[trend['best']],
        'trend': {'slope': round(trend['slope_decade'], 3), 'r2': round(trend['r2'], 3), 'p2050': round(float(trend['chosen'][-1]), 2)},
        'anomaly': {'mean': round(anomalies['mean'], 3) + 0.0, 'std': round(anomalies['std'], 3), 'count': len(anomalies['flagged'])},
        'regimes': regimes['summary'], 'regime_members': regimes['members'],
        'corr_labels': corr['labels'],
        'corr_rows': [{'label': l, 'cells': row} for l, row in zip(corr['labels'], corr['matrix'])],
        'data_through': int(annual.index.max()),
    })


# ---------------------------------------------------------------- feedback / support
@login_required(login_url=LOGIN)
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
            item = Feedback(user=request.user, category=category, subject=subject)
            item.message = message
            item.save()
            audit(request, 'feedback', subject)
            messages.success(request, 'Thanks - your message was sent to the agency team.')
            return redirect('climate:feedback')
    return render(request, 'climate/feedback.html', {'categories': Feedback.CATEGORIES, 'items': Feedback.objects.filter(user=request.user)})


# ---------------------------------------------------------------- help
@login_required(login_url=LOGIN)
def help_page(request):
    return render(request, 'climate/help.html', {'catalogue': analytics.catalogue()})


# ---------------------------------------------------------------- administration
def _parse_upload(upload, value_column):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError('The file is larger than 2 MB.')
    name = upload.name.lower()
    raw = upload.read()
    if name.endswith('.csv'):
        frame = pd.read_csv(io.BytesIO(raw))
    elif name.endswith('.json'):
        parsed = json.loads(raw.decode('utf-8'))
        frame = pd.DataFrame(parsed if isinstance(parsed, list) else parsed.get('data', parsed))
    elif name.endswith('.xls'):
        frame = pd.read_excel(io.BytesIO(raw))
    else:
        raise ValueError('Supported formats: .csv, .json, .xls')
    if frame.shape[1] < 2:
        raise ValueError('The file needs at least two columns: a year/date and a value.')
    time_col = next((c for c in frame.columns if re.search(r'year|date|time', str(c), re.I)), frame.columns[0])
    numeric = [c for c in frame.columns if c != time_col and pd.api.types.is_numeric_dtype(frame[c])]
    value_col = value_column if value_column in frame.columns else (numeric[0] if numeric else None)
    if value_col is None:
        raise ValueError('No numeric value column found.')
    when = frame[time_col]
    years = pd.to_numeric(when, errors='coerce')
    if years.isna().mean() > 0.5:
        years = pd.to_datetime(when, errors='coerce').dt.year
    frame = pd.DataFrame({'year': years, 'value': pd.to_numeric(frame[value_col], errors='coerce')}).dropna()
    frame = frame[(frame['year'] >= 1000) & (frame['year'] <= 2200)]
    frame['year'] = frame['year'].astype(int)
    frame = frame.groupby('year', as_index=False)['value'].mean().sort_values('year')
    if len(frame) < 3:
        raise ValueError('Fewer than 3 usable rows after cleaning.')
    return [[int(y), round(float(v), 4)] for y, v in zip(frame['year'], frame['value'])]


@admin_required
def admin_panel(request):
    ensure_thresholds()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'thresholds':
            changed = []
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
                if value != threshold.value:
                    changed.append(f'{threshold.key}={value:g}')
                threshold.value = value
                threshold.save()
            audit(request, 'thresholds', ', '.join(changed) or 'no changes')
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
                audit(request, 'respond', item.subject)
                messages.success(request, 'Response saved.')
        elif action == 'upload':
            title = request.POST.get('title', '').strip()[:120]
            upload = request.FILES.get('file')
            if not title or not upload:
                messages.error(request, 'Give the dataset a title and choose a file.')
            else:
                try:
                    points = _parse_upload(upload, request.POST.get('value_column', '').strip())
                except Exception as exc:
                    messages.error(request, f'Could not read that file: {exc}')
                else:
                    slug, n = slugify(title) or 'dataset', 1
                    while CustomDataset.objects.filter(slug=slug).exists():
                        n += 1
                        slug = f'{slugify(title)}-{n}'
                    visibility = request.POST.get('visibility', 'analysts')
                    CustomDataset.objects.create(slug=slug, title=title, unit=request.POST.get('unit', '').strip()[:30],
                                                 source=request.POST.get('source', '').strip()[:200],
                                                 visibility=visibility if visibility in ('analysts', 'admins') else 'analysts',
                                                 points=points, uploaded_by=request.user.username)
                    audit(request, 'upload', f'{title} ({len(points)} yearly points)')
                    messages.success(request, f'Added "{title}" with {len(points)} yearly values to the Data explorer.')
        elif action == 'delete_dataset':
            CustomDataset.objects.filter(slug=request.POST.get('slug', '')).delete()
            audit(request, 'delete_dataset', request.POST.get('slug', ''))
            messages.success(request, 'Dataset removed.')
        return redirect('climate:admin_panel')

    data = analytics.dashboard_data(thresholds=current_thresholds())
    return render(request, 'climate/admin_panel.html', {
        'thresholds': AlertThreshold.objects.all(), 'alerts': data['alerts'], 'feedback_items': Feedback.objects.select_related('user'),
        'custom': CustomDataset.objects.all(), 'audit': AuditLog.objects.all()[:25],
        'users': User.objects.order_by('username').prefetch_related('groups'),
    })


@admin_required
def backup_download(request):
    """Zip of a consistent database snapshot, the data lake and its manifest."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        db_name = connection.settings_dict['NAME']
        fd, snapshot = tempfile.mkstemp(suffix='.sqlite3')
        os.close(fd)
        try:
            source, dest = sqlite3.connect(str(db_name)), sqlite3.connect(snapshot)
            with dest:
                source.backup(dest)
            source.close()
            dest.close()
            archive.write(snapshot, 'database.sqlite3')
        finally:
            os.unlink(snapshot)
        for root, _, files in os.walk(lake.LAKE_DIR):
            for fname in files:
                full = os.path.join(root, fname)
                archive.write(full, os.path.join('lake', os.path.relpath(full, lake.LAKE_DIR)))
        archive.writestr('README.txt', f'EarthScape Climate Agency backup created {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n')
    buffer.seek(0)
    audit(request, 'backup', 'downloaded full backup')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')
    return FileResponse(buffer, as_attachment=True, filename=f'earthscape-backup-{stamp}.zip', content_type='application/zip')


@admin_required
def monitor_page(request):
    return render(request, 'climate/monitor.html', {'lake_kb': round(lake.lake_size_bytes() / 1024), 'datasets': len(lake.load_manifest())})


@admin_required
def monitor_data(request):
    return JsonResponse(monitor.snapshot())
