from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from .models import *
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

#---------------for login registration---------------
from django.contrib.auth.decorators import login_required

from django.contrib import messages

from django.contrib.auth import authenticate, login, logout

from django.contrib.auth.models import User, Group
from django.core.mail import send_mail
from django.urls import reverse

from .forms import CustomerRegistrationForm, CreateUserForm, ProfileUpdateForm

from django.contrib.auth.hashers import make_password, check_password


def index(request):
    return render(request, "climatechanges/index.html", _landing_data())


def about(request):
    return render(request, "climatechanges/pages/about.html")


def signup(request):
    """Register: CreateUserForm makes the login account, CustomerRegistrationForm the profile."""
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        user_form = CreateUserForm(request.POST)
        customer_form = CustomerRegistrationForm(request.POST)
        if user_form.is_valid() and customer_form.is_valid():
            user = user_form.save()
            from .roles import ANALYST, assign_role
            assign_role(user, ANALYST)   # default role: Climate Analyst

            customer = customer_form.save(commit=False)
            customer.user = user
            customer.username = user.username
            customer.email = user.email
            customer.password = make_password(user_form.cleaned_data["password1"])
            customer.save()

            messages.success(request, "Your account has been created successfully. Please log in.")
            return redirect("login")
    else:
        user_form = CreateUserForm()
        customer_form = CustomerRegistrationForm()

    errors = [e for f in (user_form, customer_form) for errs in f.errors.values() for e in errs]
    context = {
        "user_form": user_form,
        "customer_form": customer_form,
        "form_errors": errors,
        "form_data": request.POST if request.method == "POST" else {},
    }
    return render(request, "climatechanges/signup.html", context)


def login_view(request):
    """Log in with Django's authenticate()."""
    if request.user.is_authenticated:
        return redirect("index")

    context = {}
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is None:
            # older accounts: password only stored (hashed) on the Customer record
            customer = Customer.objects.filter(username__iexact=username).first()
            if customer and check_password(password, customer.password):
                user = customer.user

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return HttpResponseRedirect(next_url)
            return redirect("console_overview")

        messages.error(request, "Wrong username or password.")
        context = {"username": username}
    return render(request, "climatechanges/login.html", context)


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("index")


@login_required
def profile(request):
    """View and update your profile with ProfileUpdateForm."""
    customer = Customer.objects.filter(user=request.user).first()
    if customer is None:
        customer = Customer.objects.create(
            user=request.user, username=request.user.username, email=request.user.email or "",
            full_name=request.user.first_name or request.user.username, password=request.user.password,
        )

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            request.user.email = customer.email
            request.user.first_name = customer.full_name or ""
            request.user.save(update_fields=["email", "first_name"])
            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
    else:
        form = ProfileUpdateForm(instance=customer)

    role = "Administrator" if request.user.is_staff else "Analyst"
    return render(request, "climatechanges/profile.html", {"form": form, "customer": customer, "role": role})


from .hdfs import read_dataset, hdfs_listing


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


from django.contrib.auth.decorators import login_required


def _disaster_rows():
    disasters, src = read_dataset("Disaster.csv")
    totals = [r for r in disasters if r["Indicator"].endswith("Number of Disasters: TOTAL")]
    return disasters, [r for r in totals if r.get("ISO2")], src


YEARS = [str(y) for y in range(1980, 2025)]


@login_required
def dataset(request):
    disasters, countries, src1 = _disaster_rows()
    carbon, src2 = read_dataset("Carbon.csv")
    years = YEARS

    # customizable view: filter everything by one country (?country=NG)
    country_list = sorted({(r["ISO2"], r["Country"]) for r in countries}, key=lambda c: c[1])
    selected = request.GET.get("country", "").upper()
    sel_name = dict(country_list).get(selected)
    if not sel_name:
        selected = ""
    scope = [r for r in countries if not selected or r["ISO2"] == selected]
    per_year = [int(sum(_num(r.get(y)) for r in scope)) for y in years]

    types = ["Flood", "Storm", "Drought", "Extreme temperature", "Landslide", "Wildfire"]
    by_type = []
    for t in types:
        rows = [r for r in disasters if r.get("ISO2") and (not selected or r["ISO2"] == selected)
                and r["Indicator"].endswith(f"Number of Disasters: {t}")]
        by_type.append(int(sum(_num(r.get(y)) for r in rows for y in years)))

    ranked = sorted(
        ({"country": r["Country"], "iso": r["ISO2"], "total": int(sum(_num(r.get(y)) for y in years))} for r in countries),
        key=lambda x: x["total"], reverse=True,
    )[:10]

    c_years = [str(y) for y in range(1992, 2024)]
    world = next((r for r in carbon if r["Country"] == "World" and r["Indicator"] == "Carbon stocks in forests"), None)
    carbon_vals = [round(_num(world.get(f"F{y}")), 1) for y in c_years] if world else []

    analytics = _analytics(years, per_year)

    # download insights as CSV (?export=csv)
    if request.GET.get("export") == "csv":
        import csv as _csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="earthscape_insights_{selected or "world"}.csv"'
        w = _csv.writer(resp)
        w.writerow(["Scope", sel_name or "All countries"])
        w.writerow(["Trend (disasters/year)", analytics["trend_slope"]])
        w.writerow(["Correlation with time (r)", analytics["correlation"]])
        w.writerow([])
        w.writerow(["Year", "Disasters", "Type"])
        for y, v in zip(years, per_year):
            w.writerow([y, v, "recorded"])
        for y, v in zip(analytics["future_years"], analytics["forecast"]):
            w.writerow([y, v, "forecast"])
        w.writerow([])
        w.writerow(["Anomaly year", "Disasters", "z-score"])
        for a in analytics["anomalies"]:
            w.writerow([a["year"], a["value"], a["z"]])
        return resp

    context = {
        "source": "hdfs" if src1 == src2 == "hdfs" else "local",
        "hdfs_files": hdfs_listing(),
        "years": years, "per_year": per_year,
        "types": types, "by_type": by_type,
        "top": ranked,
        "c_years": c_years, "carbon_vals": carbon_vals,
        "total_disasters": sum(per_year),
        "n_countries": len(scope),
        "n_rows": len(disasters) + len(carbon),
        "country_list": country_list, "selected": selected, "sel_name": sel_name,
        "role": "Administrator" if request.user.is_staff else "Analyst",
    }
    context.update(analytics)

    # administrator panel
    if request.user.is_staff:
        from .models import Feedback as _F
        context["admin_stats"] = {
            "users": User.objects.count(),
            "open_feedback": _F.objects.filter(resolved=False).count(),
            "recent": _F.objects.order_by("-created")[:5],
        }
    return render(request, "climatechanges/dataset.html", context)


def _landing_data():
    """Real numbers + forecast + alerts for the landing page (cached in memory)."""
    global _LANDING
    try:
        return _LANDING
    except NameError:
        pass
    _, countries, src = _disaster_rows()
    per_year = [int(sum(_num(r.get(y)) for r in countries)) for y in YEARS]
    a = _analytics(YEARS, per_year)
    # build SVG polyline points for a 600x180 chart (recorded + forecast)
    vals = per_year + a["forecast"]
    hi = max(vals) or 1
    n = len(vals)
    pts = [(round(i * 600 / (n - 1), 1), round(170 - v / hi * 150, 1)) for i, v in enumerate(vals)]
    k = len(per_year)
    _LANDING = {
        "spark_recorded": " ".join(f"{x},{y}" for x, y in pts[:k]),
        "spark_area": f"0,180 " + " ".join(f"{x},{y}" for x, y in pts[:k]) + f" {pts[k-1][0]},180",
        "spark_forecast": " ".join(f"{x},{y}" for x, y in pts[k-1:]),
        "spark_last": pts[-1], "spark_now": pts[k-1],
        "land_forecast_year": a["future_years"][-1], "land_forecast": a["forecast"][-1],
        "land_slope": a["trend_slope"], "land_alerts": a["alerts"],
        "land_latest": per_year[-1], "land_total": sum(per_year),
        "land_country_count": len({r.get("ISO3") for r in countries if r.get("ISO3")}),
        "land_first_year": YEARS[0], "land_last_year": YEARS[-1],
    }
    return _LANDING


def _analytics(years, values, threshold=2.0):
    """Trend prediction (linear regression), anomaly detection (z-score) and alerts."""
    import numpy as np
    x = np.array([int(y) for y in years], dtype=float)
    y = np.array(values, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    future = [int(x[-1]) + i for i in range(1, 6)]
    forecast = [max(0, round(slope * f + intercept)) for f in future]
    # anomalies: residual from trend more than `threshold` std devs
    resid = y - (slope * x + intercept)
    z = (resid - resid.mean()) / (resid.std() or 1)
    anomalies = [{"year": int(x[i]), "value": int(y[i]), "z": round(float(z[i]), 2)}
                 for i in range(len(x)) if abs(z[i]) >= threshold]
    corr = float(np.corrcoef(x, y)[0, 1])
    alerts = []
    if slope > 0:
        alerts.append(f"Rising trend: about {slope:.1f} more climate disasters every year.")
    if forecast and forecast[-1] > y.max():
        alerts.append(f"Forecast for {future[-1]} ({forecast[-1]}) exceeds the highest year on record ({int(y.max())}).")
    for a in anomalies:
        alerts.append(f"Anomaly in {a['year']}: {a['value']} disasters (z = {a['z']}).")
    return {
        "trend_slope": round(float(slope), 2), "correlation": round(corr, 2),
        "future_years": [str(f) for f in future], "forecast": forecast,
        "anomalies": anomalies, "alerts": alerts,
    }


from django.http import Http404
from django.template.loader import get_template
from django.template import TemplateDoesNotExist


def page(request, name):
    """Serve any converted site page, e.g. /climatechanges/quiz.html"""
    if name == "index":
        return index(request)
    template = f"climatechanges/pages/{name}.html"
    try:
        get_template(template)
    except TemplateDoesNotExist:
        raise Http404("Page not found")
    return render(request, template)


from .models import Feedback


def support(request):
    sent = False
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:100]
        email = request.POST.get("email", "").strip()[:100]
        kind = request.POST.get("kind", "feedback")
        message = request.POST.get("message", "").strip()
        if name and email and message:
            Feedback.objects.create(name=name, email=email, kind=kind, message=message)
            sent = True
    return render(request, "climatechanges/support.html", {"sent": sent, "types": Feedback.TYPES})


# ---------------------------------------------------------------------------
# EarthScape Assistant (chatbot)
# ---------------------------------------------------------------------------
import json as _json

from django.http import JsonResponse as _JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie as _ensure_csrf
from django.views.decorators.http import require_http_methods as _require_methods


@_ensure_csrf
@_require_methods(["GET", "POST"])
def chat_api(request):
    """GET: widget bootstrap (sets the CSRF cookie). POST: {"messages": [{"role", "content"}, ...]} -> {"reply"}."""
    from . import chatbot
    if request.method == "GET":
        return _JsonResponse({"ai": chatbot.enabled()})
    if len(request.body) > 8000:
        return _JsonResponse({"error": "Message too long."}, status=413)
    try:
        payload = _json.loads(request.body or b"{}")
    except ValueError:
        return _JsonResponse({"error": "Invalid request."}, status=400)
    forwarded = request.META.get("X-FORWARDED-FOR", request.META.get("HTTP_X_FORWARDED_FOR", ""))
    visitor = (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "?"))[:45]
    page = payload.get("page") if payload.get("page") in chatbot.PAGE_HINTS else ""
    text, source = chatbot.reply(payload.get("messages"), visitor, page)
    return _JsonResponse({"reply": text, "source": source})
