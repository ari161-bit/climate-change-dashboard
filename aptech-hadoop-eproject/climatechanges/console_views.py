"""EarthScape console: the logged-in climate intelligence platform (sidebar sections)."""
import json
import logging
from pathlib import Path

import numpy as np
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import alerts as alert_engine
from . import datasources, hadoop, ingestion, live, ml, reports, resources
from .forms import (AlertRuleForm, DatasetUploadForm, ProfileUpdateForm, SupportReplyForm,
                    SupportRequestForm)
from .mapreduce import run_job
from .models import (Alert, AlertRule, Customer, Dataset, Feedback, ModelRun, ProcessingJob,
                     RequestMetric, SensorReading)
from .roles import ADMIN, ANALYST, admin_required, api_login_required, assign_role, is_admin, role_of

log = logging.getLogger("earthscape")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _version():
    """Changes whenever data changes, so cached analytics refresh automatically."""
    agg = SensorReading.objects.aggregate(n=Count("id"), m=Max("id"))
    return f"{agg['n']}-{agg['m']}-{datasources._mtime('Temperature.csv')}-{datasources._mtime('Disaster.csv')}"


def cached(name, fn, *args, timeout=900):
    key = f"es:{name}:{_version()}:{':'.join(map(str, args))}"
    val = cache.get(key)
    if val is None:
        val = fn(*args)
        cache.set(key, val, timeout)
    return val


def _filters(request):
    g = request.GET
    return {"start": g.get("start", ""), "end": g.get("end", ""), "country": g.get("country", ""),
            "region": g.get("region", ""), "variable": g.get("variable", "temperature")}


def _filter_options():
    return {
        "reading_countries": list(SensorReading.objects.exclude(country="").values_list("country", flat=True)
                                  .distinct().order_by("country")),
        "regions": datasources.REGIONS,
        "variables": [("temperature", "Temperature (°C)"), ("rainfall", "Rainfall (mm)"),
                      ("humidity", "Humidity (%)"), ("co2", "CO₂ (ppm)")],
        "fao_countries": cached("fao_countries", datasources.countries),
    }


def _monthly(qs, variable):
    rows = (qs.exclude(**{f"{variable}__isnull": True}).annotate(m=TruncMonth("timestamp")).values("m")
            .annotate(v=Avg(variable)).order_by("m"))
    return [r["m"].strftime("%Y-%m") for r in rows], [round(r["v"], 2) for r in rows]


def _sources(qs):
    return datasources.data_badge(set(qs.values_list("source", flat=True).distinct()))


def ctx(request, section, **extra):
    base = {"section": section, "role": role_of(request.user), "is_admin": is_admin(request.user),
            "unread_alerts": alert_engine.unread_for(request.user).count(),
            "latest_alerts": alert_engine.unread_for(request.user)[:5]}
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# 1. Overview
# ---------------------------------------------------------------------------
@login_required
def overview(request):
    f = _filters(request)
    qs = datasources.filtered_readings(f)
    world = cached("world_series", lambda: datasources.world_temperature_series("World").to_dict("list"))
    last_i = len(world["year"]) - 1
    prev10 = float(np.mean(world["anomaly"][max(0, last_i - 10):last_i])) if last_i > 0 else 0
    agg = qs.aggregate(t=Avg("temperature"), r=Avg("rainfall"), rmax=Max("rainfall"), rsum=Sum("rainfall"),
                       h=Avg("humidity"), hmin=Min("humidity"), hmax=Max("humidity"), n=Count("id"))
    co2 = cached("co2", live.co2_series)
    if not co2:
        c = qs.exclude(co2__isnull=True).order_by("-timestamp").values_list("co2", "source").first()
        co2 = {"latest": c[0], "label": datasources.data_badge({c[1]}), "source": "station readings"} if c else None
    anomaly_job = ProcessingJob.objects.filter(job_type="anomaly_scan", status="success").first()
    jobs = ProcessingJob.objects.aggregate(n=Count("id"), ok=Count("id", filter=Q(status="success")),
                                           recs=Sum("records_in"), ms=Avg("duration_ms"))
    months, values = _monthly(qs, f["variable"])
    tt = cached("trend", ml.temperature_trend, "World")
    return render(request, "climatechanges/console/overview.html", ctx(
        request, "overview", f=f, opts=_filter_options(),
        world_latest_year=world["year"][-1], world_latest=world["anomaly"][-1], world_prev10=round(prev10, 2),
        agg=agg, data_label=_sources(qs), co2=co2,
        anomalies=(anomaly_job.records_out if anomaly_job else None),
        jobs=jobs, datasets=Dataset.objects.count(), readings=SensorReading.objects.count(),
        recent_alerts=Alert.objects.all()[:6],
        chart={"world_years": world["year"], "world_values": world["anomaly"],
               "future_years": tt["future_years"] if tt else [], "forecast": tt["forecast"] if tt else [],
               "months": months, "values": values, "variable": f["variable"]},
        hdfs=hadoop.status(), mongo=mongo_status(),
    ))


# ---------------------------------------------------------------------------
# 2. Climate analytics
# ---------------------------------------------------------------------------
@login_required
def analytics(request):
    f = _filters(request)
    qs = datasources.filtered_readings(f)
    fao_country = request.GET.get("fao_country", "World")
    t = datasources.world_temperature_series(fao_country)
    y0 = int(f["start"][:4]) if f["start"][:4].isdigit() else None
    y1 = int(f["end"][:4]) if f["end"][:4].isdigit() else None
    if y0:
        t = t[t["year"] >= y0]
    if y1:
        t = t[t["year"] <= y1]

    by_station = list(qs.exclude(rainfall__isnull=True).values("station", "region")
                      .annotate(mean=Avg("rainfall"), mx=Max("rainfall")).order_by("-mean"))
    by_region_h = list(qs.exclude(humidity__isnull=True).annotate(m=TruncMonth("timestamp"))
                       .values("region").annotate(h=Avg("humidity")).order_by("region"))
    hum_months = {}
    for reg in datasources.REGIONS:
        m, v = _monthly(qs.filter(region=reg), "humidity")
        if m:
            hum_months[reg] = {"months": m, "values": v}
    co2 = cached("co2", live.co2_series)
    co2_chart = ({"labels": co2["months"][-240:], "values": co2["values"][-240:], "label": co2["label"],
                  "source": co2["source"]} if co2 else None)
    if not co2_chart:
        m, v = _monthly(qs, "co2")
        co2_chart = {"labels": m, "values": v, "label": _sources(qs.exclude(co2__isnull=True)), "source": "station readings"}
    pat = cached("patterns", ml.patterns)
    year, cur = cached("latest_anoms", datasources.latest_country_anomalies)
    trend = cached("trend", ml.temperature_trend, fao_country)
    return render(request, "climatechanges/console/analytics.html", ctx(
        request, "analytics", f=f, opts=_filter_options(), fao_country=fao_country,
        data_label=_sources(qs),
        charts={
            "temp": {"years": t["year"].tolist(), "values": [round(v, 3) for v in t["anomaly"].tolist()],
                     "country": fao_country},
            "rain": {"stations": [r["station"] for r in by_station], "mean": [round(r["mean"], 1) for r in by_station],
                     "max": [round(r["mx"], 1) for r in by_station]},
            "humidity": hum_months,
            "co2": co2_chart,
            "regional": {"decades": [f"{d}s" for d in pat["decades"]],
                         "rows": [{"region": r["region"], "values": r["values"]} for r in pat["rows"]]},
            "map": {"year": year, "iso3": cur["ISO3"].tolist(), "names": cur["Country"].tolist(),
                    "values": [None if v != v else round(float(v), 2) for v in cur["anomaly"]]},
            "hvp": ({"years": trend["years"], "actual": trend["actual"], "fitted": trend["fitted"],
                     "future": trend["future_years"], "forecast": trend["forecast"],
                     "band": trend["forecast_band"], "model": trend["best_model"]} if trend else None),
        },
        patterns=pat, by_region_h=by_region_h,
    ))


# ---------------------------------------------------------------------------
# 3. Data management (ingestion)
# ---------------------------------------------------------------------------
@login_required
def data_management(request):
    form = DatasetUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            ds = ingestion.create_dataset(form.cleaned_data["file"], form.cleaned_data["name"],
                                          form.cleaned_data["kind"], form.cleaned_data["description"], request.user)
            messages.success(request, f"“{ds.name}” uploaded and validated: {ds.rows} rows, "
                                      f"{ds.missing_values} missing values, {ds.duplicate_rows} duplicates.")
            return redirect("console_dataset", pk=ds.pk)
        except ingestion.ValidationError as e:
            messages.error(request, f"Upload rejected: {e}")
            log.info("Upload rejected for %s: %s", request.user, e)
    page = Paginator(Dataset.objects.select_related("uploaded_by"), 15).get_page(request.GET.get("page"))
    return render(request, "climatechanges/console/data.html", ctx(
        request, "data", form=form, page=page, max_mb=settings.MAX_UPLOAD_MB,
        source_counts=list(SensorReading.objects.values("source").annotate(n=Count("id")).order_by("-n")),
        ingest_token_hint=settings.INGEST_API_TOKEN[:4] + "…" if is_admin(request.user) else None,
    ))


@login_required
def dataset_detail(request, pk):
    ds = get_object_or_404(Dataset, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "clean":
                r = ingestion.clean(ds)
                messages.success(request, f"Cleaned: removed {r['removed_rows']} rows, filled "
                                          f"{sum(r['filled_numeric'].values())} numeric gaps.")
            elif action == "store":
                backend, path = ingestion.store(ds)
                if backend == "hdfs":
                    messages.success(request, f"Stored in HDFS at {path}.")
                else:
                    messages.warning(request, f"HDFS is not running, so the file was saved to the local staging "
                                              f"area that mirrors the HDFS layout: {path}")
            elif action == "import":
                n, skipped, new_alerts = ingestion.import_readings(ds)
                messages.success(request, f"Imported {n} readings ({skipped} skipped); {new_alerts} new alerts.")
            elif action == "delete" and (is_admin(request.user) or ds.uploaded_by_id == request.user.id):
                from . import mongo
                mongo.delete_dataset(ds.pk)
                ds.delete()
                messages.success(request, "Dataset deleted.")
                return redirect("console_data")
        except ingestion.ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            log.exception("Dataset action %s failed", action)
            messages.error(request, f"Action failed: {e}")
        return redirect("console_dataset", pk=ds.pk)
    return render(request, "climatechanges/console/dataset_detail.html", ctx(request, "data", ds=ds, p=ds.profile))


@login_required
def dataset_download(request, pk, which):
    ds = get_object_or_404(Dataset, pk=pk)
    f = ds.cleaned_file if which == "clean" else ds.file
    if not f:
        raise Http404
    name = Path(f.name).name if which == "clean" else ds.original_filename
    log.info("Dataset %s (%s) downloaded by %s", ds.pk, which, request.user)
    content_type = ("text/csv" if name.endswith(".csv") else
                    "image/tiff" if name.lower().endswith((".tif", ".tiff")) else "application/json")
    resp = HttpResponse(ingestion.read_bytes(f), content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="{name}"'
    return resp


# ---------------------------------------------------------------------------
# 4. Data processing (Hadoop / MapReduce)
# ---------------------------------------------------------------------------
@login_required
def processing(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "run":
            job = run_job(request.POST.get("job_type"), request.user)
            (messages.success if job.status == "success" else messages.error)(
                request, f"{job.get_job_type_display()}: {job.status} in {job.duration_ms} ms"
                         f"{' - ' + job.error if job.error else ''}")
            return redirect("console_job", pk=job.pk)
        if action == "pull_live":
            n, errors = live.pull_weather()
            co2 = live.co2_series(refresh=True)
            if errors:
                messages.warning(request, "; ".join(errors))
            else:
                messages.success(request, f"Pulled {n} live readings from Open-Meteo"
                                          f"{' and refreshed NOAA CO₂' if co2 else ''}.")
        if action == "backup" and is_admin(request.user):
            from .management.commands.backup_earthscape import make_backup
            path = make_backup()
            messages.success(request, f"Backup created: {Path(path).name}")
        return redirect("console_processing")

    since = timezone.now() - timezone.timedelta(hours=24)
    m = RequestMetric.objects.filter(created__gte=since)
    durations = sorted(m.values_list("duration_ms", flat=True))
    perf = {"requests": len(durations),
            "avg": round(sum(durations) / len(durations)) if durations else 0,
            "p95": durations[int(len(durations) * 0.95) - 1] if durations else 0,
            "errors": m.filter(status__gte=500).count(),
            "slow": list(m.values("path").annotate(avg=Avg("duration_ms"), n=Count("id")).order_by("-avg")[:5])}
    db = Path(settings.DATABASES["default"]["NAME"])
    log_tail = []
    if is_admin(request.user):
        lf = Path(settings.LOG_DIR) / "earthscape.log"
        if lf.exists():
            log_tail = lf.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
    backups = sorted(Path(settings.BACKUP_DIR).glob("earthscape_*.zip*"))[-5:] if Path(settings.BACKUP_DIR).exists() else []
    return render(request, "climatechanges/console/processing.html", ctx(
        request, "processing", hdfs=hadoop.status(), jobs=ProcessingJob.objects.select_related("started_by")[:20],
        job_types=ProcessingJob.JOB_TYPES, perf=perf, db_mb=round(db.stat().st_size / 1e6, 2) if db.exists() else 0,
        totals=ProcessingJob.objects.aggregate(n=Count("id"), recs=Sum("records_in"), ms=Avg("duration_ms")),
        readings=SensorReading.objects.count(), log_tail=log_tail, backups=[b.name for b in reversed(backups)],
        staging=str(settings.HDFS_STAGING_DIR), mongo=mongo_status(),
        res=resources.snapshot(),
        res_chart=_resource_chart(),
    ))


def mongo_status():
    from . import mongo
    return mongo.status()


def _resource_chart():
    from .models import ResourceSnapshot
    rows = list(ResourceSnapshot.objects.filter(created__gte=timezone.now() - timezone.timedelta(hours=24))
                .order_by("created").values("created", "cpu_pct", "mem_pct", "disk_pct"))
    return {"labels": [timezone.localtime(r["created"]).strftime("%H:%M") for r in rows],
            "cpu": [r["cpu_pct"] for r in rows], "mem": [r["mem_pct"] for r in rows], "disk": [r["disk_pct"] for r in rows]}


@login_required
def job_detail(request, pk):
    job = get_object_or_404(ProcessingJob, pk=pk)
    out = job.result.get("output", {})
    chart = None
    if out and job.job_type in ("yearly_temperature", "disasters_per_year", "hadoop_disasters_per_year"):
        keys = list(out.keys())
        vals = [v["mean"] if isinstance(v, dict) else v for v in out.values()]
        chart = {"labels": keys, "values": vals}
    return render(request, "climatechanges/console/job_detail.html", ctx(
        request, "processing", job=job, chart=chart,
        rows=list(out.items())[:200], result_json=json.dumps(job.result, indent=2)[:20000]))


# ---------------------------------------------------------------------------
# 5. Predictions (ML)
# ---------------------------------------------------------------------------
@login_required
def predictions(request):
    if request.method == "POST":
        job = run_job("train_models", request.user)
        (messages.success if job.status == "success" else messages.error)(
            request, f"Models retrained in {job.duration_ms} ms.")
        return redirect("console_predictions")
    country = request.GET.get("country", "World")
    tt = cached("trend", ml.temperature_trend, country)
    rf = cached("rainfall", ml.rainfall_model)
    return render(request, "climatechanges/console/predictions.html", ctx(
        request, "predictions", country=country, tt=tt, rf=rf, opts=_filter_options(),
        runs=ModelRun.objects.all()[:12],
        chart={"tt": tt, "rf": rf if rf.get("ready") else None},
    ))


# ---------------------------------------------------------------------------
# 6. Anomaly detection
# ---------------------------------------------------------------------------
@login_required
def anomalies(request):
    try:
        z = float(request.GET.get("z", 2.5))
    except ValueError:
        z = 2.5
    z = min(max(z, 1.5), 5.0)
    an = cached("anomalies", lambda zz: ml.anomaly_detection(z_threshold=zz), z)
    corr = cached("corr", ml.correlation_analysis)
    year, cur = cached("latest_anoms", datasources.latest_country_anomalies)
    flagged = {a["iso3"] for a in an["anomalies"] if a["type"] == "temperature" and a["year"] == year}
    return render(request, "climatechanges/console/anomalies.html", ctx(
        request, "anomalies", an=an, corr=corr, z=z,
        temp_anoms=[a for a in an["anomalies"] if a["type"] == "temperature"],
        station_anoms=[a for a in an["anomalies"] if a["type"] == "station"],
        chart={"map": {"year": year, "iso3": cur["ISO3"].tolist(), "names": cur["Country"].tolist(),
                       "z": [None if v != v else round(float(v), 2) for v in cur["z"]],
                       "values": [None if v != v else round(float(v), 2) for v in cur["anomaly"]],
                       "flagged": sorted(flagged)},
               "scatter": corr["scatter"], "matrix": corr["matrix"]},
    ))


# ---------------------------------------------------------------------------
# 7. Alerts
# ---------------------------------------------------------------------------
@login_required
def alerts_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "mark_all":
            for a in alert_engine.unread_for(request.user):
                a.read_by.add(request.user)
            messages.success(request, "All alerts marked as read.")
        elif action in ("read", "unread"):
            a = get_object_or_404(Alert, pk=request.POST.get("id"))
            (a.read_by.add if action == "read" else a.read_by.remove)(request.user)
        elif action == "evaluate":
            job = run_job("evaluate_alerts", request.user)
            messages.success(request, f"Evaluated rules: {job.result.get('new_alerts', 0)} new alerts.")
        elif action == "save_rule" and is_admin(request.user):
            rule = get_object_or_404(AlertRule, pk=request.POST["rule_id"]) if request.POST.get("rule_id") else None
            form = AlertRuleForm(request.POST, instance=rule)
            if form.is_valid():
                r = form.save(commit=False)
                r.created_by = r.created_by or request.user
                r.save()
                messages.success(request, f"Rule “{r.name}” saved.")
            else:
                messages.error(request, "Rule not saved: " + "; ".join(e for errs in form.errors.values() for e in errs))
        elif action == "delete_rule" and is_admin(request.user):
            AlertRule.objects.filter(pk=request.POST.get("rule_id")).delete()
            messages.success(request, "Rule deleted.")
        return redirect(request.get_full_path())

    qs = Alert.objects.all()
    sev, cat, state = request.GET.get("severity"), request.GET.get("category"), request.GET.get("state")
    if sev:
        qs = qs.filter(severity=sev)
    if cat:
        qs = qs.filter(category=cat)
    if state == "unread":
        qs = qs.exclude(read_by=request.user)
    elif state == "read":
        qs = qs.filter(read_by=request.user)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    read_ids = set(request.user.read_alerts.filter(id__in=[a.id for a in page]).values_list("id", flat=True))
    return render(request, "climatechanges/console/alerts.html", ctx(
        request, "alerts", page=page, read_ids=read_ids, rules=AlertRule.objects.all(), rule_form=AlertRuleForm(),
        counts=Alert.objects.aggregate(total=Count("id"), critical=Count("id", filter=Q(severity="critical")),
                                       warning=Count("id", filter=Q(severity="warning")),
                                       info=Count("id", filter=Q(severity="info"))),
        sev=sev, cat=cat, state=state, severities=AlertRule.SEVERITIES,
    ))


# ---------------------------------------------------------------------------
# 8. Reports
# ---------------------------------------------------------------------------
@login_required
def reports_view(request):
    kind = request.GET.get("kind")
    fmt = request.GET.get("format")
    country = request.GET.get("country", "World")
    if kind == "tableau":
        log.info("Tableau extract generated by %s", request.user)
        resp = HttpResponse(reports.tableau_extract(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="earthscape_tableau_extract_{timezone.now():%Y%m%d}.zip"'
        return resp
    if kind in reports.REPORTS and fmt in ("csv", "pdf"):
        rep = reports.build(kind, {"country": country})
        name = f"earthscape_{kind}_{country.replace(' ', '_')}_{timezone.now():%Y%m%d}"
        log.info("Report %s (%s) generated by %s", kind, fmt, request.user)
        if fmt == "csv":
            resp = HttpResponse(reports.to_csv(rep), content_type="text/csv")
            resp["Content-Disposition"] = f'attachment; filename="{name}.csv"'
        else:
            resp = HttpResponse(reports.to_pdf(rep), content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
        return resp
    preview = reports.build(kind, {"country": country}) if kind in reports.REPORTS else None
    return render(request, "climatechanges/console/reports.html", ctx(
        request, "reports", report_types=reports.REPORTS, kind=kind, country=country, preview=preview,
        opts=_filter_options()))


# ---------------------------------------------------------------------------
# 9. Support
# ---------------------------------------------------------------------------
@login_required
def support_view(request):
    form = SupportRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fb = form.save(commit=False)
        fb.user = request.user
        fb.name = request.user.get_full_name() or request.user.first_name or request.user.username
        fb.email = request.user.email or f"{request.user.username}@earthscape.local"
        fb.save()
        log.info("Support request %s created by %s", fb.id, request.user)
        messages.success(request, f"Request #{fb.id} submitted. You can track its status below.")
        return redirect("console_support")
    qs = Feedback.objects.select_related("user") if is_admin(request.user) else Feedback.objects.filter(user=request.user)
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    return render(request, "climatechanges/console/support.html", ctx(
        request, "support", form=form, items=qs[:100], status=status, statuses=Feedback.STATUSES,
        counts=qs.model.objects.filter(**({} if is_admin(request.user) else {"user": request.user}))
        .values("status").annotate(n=Count("id"))))


@login_required
def support_detail(request, pk):
    fb = get_object_or_404(Feedback, pk=pk)
    if not (is_admin(request.user) or fb.user_id == request.user.id):
        raise Http404
    form = SupportReplyForm(request.POST or None, instance=fb) if is_admin(request.user) else None
    if request.method == "POST" and form is not None and form.is_valid():
        obj = form.save(commit=False)
        if form.cleaned_data["admin_reply"]:
            obj.replied_by, obj.replied_at = request.user, timezone.now()
        obj.save()
        log.info("Support request %s updated by %s -> %s", fb.id, request.user, obj.status)
        messages.success(request, "Request updated.")
        return redirect("console_support_detail", pk=fb.pk)
    return render(request, "climatechanges/console/support_detail.html", ctx(request, "support", fb=fb, form=form))


# ---------------------------------------------------------------------------
# 10. Settings (+ admin user management)
# ---------------------------------------------------------------------------
@login_required
def settings_view(request):
    customer = Customer.objects.filter(user=request.user).first()
    if customer is None:
        customer = Customer.objects.create(user=request.user, username=request.user.username,
                                           email=request.user.email or "", password=request.user.password,
                                           full_name=request.user.get_full_name() or request.user.username)
    pform = ProfileUpdateForm(instance=customer)
    wform = PasswordChangeForm(request.user)
    if request.method == "POST":
        if request.POST.get("action") == "profile":
            pform = ProfileUpdateForm(request.POST, instance=customer)
            if pform.is_valid():
                pform.save()
                request.user.email, request.user.first_name = customer.email, customer.full_name or ""
                request.user.save(update_fields=["email", "first_name"])
                messages.success(request, "Profile updated.")
                return redirect("console_settings")
        elif request.POST.get("action") == "maintenance" and is_admin(request.user):
            from .models import MaintenanceNotice
            from django.utils.dateparse import parse_datetime
            start, end = parse_datetime(request.POST.get("starts_at", "")), parse_datetime(request.POST.get("ends_at", ""))
            title = request.POST.get("title", "").strip()[:150]
            if title and start and end and end > start:
                MaintenanceNotice.objects.create(title=title, message=request.POST.get("message", "")[:2000],
                                                 starts_at=timezone.make_aware(start) if timezone.is_naive(start) else start,
                                                 ends_at=timezone.make_aware(end) if timezone.is_naive(end) else end,
                                                 created_by=request.user)
                log.info("Maintenance notice '%s' scheduled by %s", title, request.user)
                messages.success(request, "Maintenance notice published to all users.")
            else:
                messages.error(request, "Give a title, a start and an end after the start.")
            return redirect("console_settings")
        elif request.POST.get("action") == "end_maintenance" and is_admin(request.user):
            from .models import MaintenanceNotice
            MaintenanceNotice.objects.filter(pk=request.POST.get("id")).update(active=False)
            messages.success(request, "Notice removed.")
            return redirect("console_settings")
        elif request.POST.get("action") == "password":
            wform = PasswordChangeForm(request.user, request.POST)
            if wform.is_valid():
                user = wform.save()
                update_session_auth_hash(request, user)
                log.info("Password changed for %s", user)
                messages.success(request, "Password changed.")
                return redirect("console_settings")
    for fld in wform.fields.values():
        fld.help_text = ""
    from .models import MaintenanceNotice
    return render(request, "climatechanges/console/settings.html", ctx(
        request, "settings", pform=pform, wform=wform, customer=customer,
        all_notices=MaintenanceNotice.objects.filter(active=True) if is_admin(request.user) else []))


@admin_required
def users_view(request):
    if request.method == "POST":
        u = get_object_or_404(User, pk=request.POST.get("user_id"))
        action = request.POST.get("action")
        if u == request.user and action in ("deactivate", "role"):
            messages.error(request, "You can't change your own role or deactivate yourself.")
        elif action == "role":
            role = request.POST.get("role")
            if role in (ADMIN, ANALYST):
                assign_role(u, role)
                log.info("%s set role of %s to %s", request.user, u, role)
                messages.success(request, f"{u.username} is now {role}.")
        elif action in ("activate", "deactivate"):
            u.is_active = action == "activate"
            u.save(update_fields=["is_active"])
            log.info("%s %sd %s", request.user, action, u)
            messages.success(request, f"{u.username} {action}d.")
        return redirect("console_users")
    q = request.GET.get("q", "").strip()
    users = User.objects.order_by("-date_joined").prefetch_related("groups")
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q))
    rows = [{"u": u, "role": role_of(u)} for u in users[:200]]
    return render(request, "climatechanges/console/users.html", ctx(request, "users", rows=rows, q=q,
                                                                   roles=[ADMIN, ANALYST]))


# ---------------------------------------------------------------------------
# REST API (JSON). All protected; ingest uses a token for machines/sensors.
# ---------------------------------------------------------------------------
@api_login_required
def api_summary(request):
    world = datasources.world_temperature_series("World")
    return JsonResponse({
        "global_temperature_anomaly": {"year": int(world["year"].iloc[-1]), "value": float(world["anomaly"].iloc[-1]),
                                       "source": datasources.TEMP_SOURCE},
        "readings": SensorReading.objects.count(),
        "datasets": Dataset.objects.count(),
        "alerts_unread": alert_engine.unread_for(request.user).count(),
        "hdfs_online": hadoop.status()["online"],
    })


@api_login_required
def api_alerts_unread(request):
    items = alert_engine.unread_for(request.user)[:8]
    return JsonResponse({"count": alert_engine.unread_for(request.user).count(),
                         "items": [{"id": a.id, "title": a.title, "severity": a.severity,
                                    "created": a.created.isoformat()} for a in items]})


@api_login_required
def api_series(request):
    f = _filters(request)
    if f["variable"] not in ("temperature", "rainfall", "humidity", "co2"):
        return JsonResponse({"error": "variable must be temperature, rainfall, humidity or co2"}, status=400)
    qs = datasources.filtered_readings(f)
    months, values = _monthly(qs, f["variable"])
    units = {"temperature": "degC", "rainfall": "mm", "humidity": "%", "co2": "ppm"}
    return JsonResponse({"variable": f["variable"], "unit": units[f["variable"]], "time_standard": "ISO 8601 month (UTC)",
                         "months": months, "values": values, "data": _sources(qs)})


@csrf_exempt
@require_POST
def api_ingest(request):
    """Real-time ingestion: POST JSON reading(s) with header X-API-Token."""
    if request.headers.get("X-API-Token") != settings.INGEST_API_TOKEN:
        return JsonResponse({"error": "invalid or missing X-API-Token"}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be JSON"}, status=400)
    items = payload if isinstance(payload, list) else [payload]
    if len(items) > 1000:
        return JsonResponse({"error": "max 1000 readings per request"}, status=413)
    from django.utils.dateparse import parse_datetime
    created, errors, new_alerts, stored = 0, [], 0, []
    rules = alert_engine._reading_rules()
    for i, it in enumerate(items):
        try:
            ts = parse_datetime(str(it.get("timestamp", ""))) or timezone.now()
            if timezone.is_naive(ts):
                ts = timezone.make_aware(ts, timezone.utc)

            def num(k):
                v = it.get(k)
                return None if v in (None, "") else float(v)

            if not it.get("station"):
                raise ValueError("station is required")
            r = SensorReading.objects.create(
                station=str(it["station"])[:100], country=str(it.get("country", ""))[:100],
                region=str(it.get("region", ""))[:50], latitude=num("latitude"), longitude=num("longitude"),
                timestamp=ts, temperature=num("temperature"), rainfall=num("rainfall"),
                humidity=num("humidity"), co2=num("co2"), source="api")
            created += 1
            new_alerts += alert_engine.check_reading(r, rules)
            stored.append(r)
        except (ValueError, TypeError) as e:
            errors.append({"index": i, "error": str(e)})
    from . import mongo
    mongo.upsert_readings(stored)
    log.info("API ingest: %d readings, %d errors, %d alerts", created, len(errors), new_alerts)
    return JsonResponse({"created": created, "errors": errors, "alerts": new_alerts},
                        status=201 if created else 400)


def api_health(request):
    """Load-balancer health check (public, no data). 200 when the app and its database answer."""
    from django.db import connection
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    from . import mongo
    body = {"status": "ok" if db_ok else "error", "database": db_ok,
            "mongodb": mongo.status()["online"], "hdfs": hadoop.status()["online"],
            "time": timezone.now().isoformat(timespec="seconds")}
    return JsonResponse(body, status=200 if db_ok else 503)


@login_required
def help_view(request):
    return render(request, "climatechanges/console/help.html", ctx(request, "help"))
