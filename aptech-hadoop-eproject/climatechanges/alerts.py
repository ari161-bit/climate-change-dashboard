"""Alert rules engine: evaluates thresholds and creates de-duplicated alerts."""
import logging

from django.utils import timezone

log = logging.getLogger("earthscape")

DEFAULT_RULES = [
    ("Extreme heat at a station", "temperature", "gt", 40.0, "critical"),
    ("Freezing temperature", "temperature", "lt", 0.0, "warning"),
    ("Heavy rainfall", "rainfall", "gt", 300.0, "warning"),
    ("Very dry month", "rainfall", "lt", 2.0, "info"),
    ("Very high humidity", "humidity", "gt", 95.0, "info"),
    ("CO₂ above 425 ppm", "co2", "gt", 425.0, "warning"),
    ("Country warming above +2.5 °C", "temp_anomaly", "gt", 2.5, "critical"),
    ("Statistical anomaly (|z| ≥ 3)", "zscore", "gt", 3.0, "warning"),
]

CATEGORY = {"temperature": "temperature", "temp_anomaly": "temperature", "rainfall": "rainfall",
            "humidity": "anomaly", "co2": "anomaly", "zscore": "anomaly"}


def seed_default_rules():
    from .models import AlertRule
    if AlertRule.objects.exists():
        return 0
    for name, var, op, thr, sev in DEFAULT_RULES:
        AlertRule.objects.create(name=name, variable=var, operator=op, threshold=thr, severity=sev)
    return len(DEFAULT_RULES)


def _create(rule, title, message, value, location, observed_at, key):
    from .models import Alert
    obj, created = Alert.objects.get_or_create(
        dedupe_key=key[:200],
        defaults=dict(rule=rule, title=title[:200], message=message, severity=rule.severity if rule else "warning",
                      category=CATEGORY.get(rule.variable, "anomaly") if rule else "anomaly",
                      value=value, location=location[:120], observed_at=observed_at))
    if created:
        from . import mongo
        mongo.upsert_alert(obj)
    return created


def _reading_rules():
    from .models import AlertRule
    return list(AlertRule.objects.filter(active=True, variable__in=["temperature", "rainfall", "humidity", "co2"]))


def check_reading(reading, rules=None):
    """Called for every newly ingested reading (real-time path)."""
    created = 0
    for rule in (rules if rules is not None else _reading_rules()):
        val = getattr(reading, rule.variable)
        if rule.matches(val):
            created += _create(
                rule, f"{rule.name}: {reading.station}",
                f"{rule.get_variable_display()} was {val:g} at {reading.station} on {reading.timestamp:%d %b %Y} "
                f"({rule.get_operator_display()} threshold {rule.threshold:g}). Source: {reading.get_source_display()}.",
                val, reading.station, reading.timestamp,
                f"r{rule.id}|{reading.station}|{reading.timestamp:%Y-%m-%d}")
    return created


def evaluate_rules(days=None):
    """Batch evaluation over stored readings and the real temperature dataset."""
    from . import datasources
    from .models import AlertRule, SensorReading

    created = 0
    qs = SensorReading.objects.all()
    if days:
        qs = qs.filter(timestamp__gte=timezone.now() - timezone.timedelta(days=days))
    from django.db.models import Q
    rules = _reading_rules()
    if rules:
        # let the database find only the readings that break at least one rule
        cond = Q()
        for rule in rules:
            cond |= Q(**{f"{rule.variable}__{'gt' if rule.operator == 'gt' else 'lt'}": rule.threshold})
        for r in qs.filter(cond).iterator():
            created += check_reading(r, rules)

    for rule in AlertRule.objects.filter(active=True, variable="temp_anomaly"):
        year, cur = datasources.latest_country_anomalies()
        for row in cur.dropna(subset=["anomaly"]).itertuples():
            if rule.matches(row.anomaly):
                created += _create(
                    rule, f"{rule.name}: {row.Country}",
                    f"{row.Country} was {row.anomaly:+.2f} °C warmer in {year} than its 1951-1980 average "
                    f"(threshold {rule.threshold:g} °C). Source: FAO (real observations).",
                    float(row.anomaly), row.Country, None, f"r{rule.id}|{row.Country}|{year}")
    log.info("Alert evaluation created %d alerts", created)
    return created


def alerts_from_anomalies(result):
    from .models import AlertRule
    created = 0
    for rule in AlertRule.objects.filter(active=True, variable="zscore"):
        for a in result["anomalies"]:
            if a["type"] == "temperature" and rule.matches(abs(a["score"])):
                created += _create(
                    rule, f"Temperature anomaly: {a['location']} {a['year']}",
                    f"{a['location']} recorded {a['value']:+.2f} °C in {a['year']}, z-score {a['score']} versus its own "
                    f"history. Source: FAO (real observations).",
                    a["value"], a["location"], None, f"z{rule.id}|{a['location']}|{a['year']}")
    return created


def unread_for(user):
    from .models import Alert
    return Alert.objects.exclude(read_by=user)
