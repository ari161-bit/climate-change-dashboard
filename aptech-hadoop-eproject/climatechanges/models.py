from django.db import models
import datetime
from django.utils import timezone
# Create your models here.
from django.contrib.auth.models import User

class Customer(models.Model):

    id =models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100, null=True)
    first_name = models.CharField(max_length=100, null=True)
    username = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=50)
    password = models.CharField(max_length=128)  # holds a Django password hash, never plain text
    address = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=50, null=True)
    state = models.CharField(max_length=50, null=True)
    country = models.CharField(max_length=50, null=True)
    zip_code = models.CharField(max_length=10, null=True)

    user=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        default=1
    )

    def __str__(self):
        return f"{self.id}: {self.full_name}: {self.username}"


class Feedback(models.Model):
    """Support request: question, problem report or feedback. Tracked until resolved."""
    TYPES = [("feedback", "Feedback"), ("issue", "Report an issue"), ("help", "Need assistance")]
    STATUSES = [("open", "Open"), ("in_progress", "In progress"), ("resolved", "Resolved")]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_requests")
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    kind = models.CharField(max_length=20, choices=TYPES, default="feedback")
    subject = models.CharField(max_length=150, blank=True, default="")
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    admin_reply = models.TextField(blank=True, default="")
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_replies")
    replied_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def save(self, *args, **kwargs):
        self.resolved = self.status == "resolved"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_kind_display()} from {self.name}"


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------
class Dataset(models.Model):
    """An uploaded climate table or catalogued GeoTIFF source and its validation result."""
    KINDS = [
        ("historical", "Historical climate dataset"),
        ("station", "Weather station records"),
        ("sensor", "Environmental sensor data"),
        ("satellite", "Satellite-derived dataset"),
    ]
    STATUSES = [("validated", "Validated"), ("invalid", "Invalid"), ("cleaned", "Cleaned"),
                ("stored", "Stored"), ("imported", "Imported")]

    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=KINDS, default="historical")
    file_format = models.CharField(max_length=10)               # csv | json
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="uploads/%Y/%m/")
    cleaned_file = models.FileField(upload_to="cleaned/%Y/%m/", blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    rows = models.PositiveIntegerField(default=0)
    columns = models.PositiveIntegerField(default=0)
    missing_values = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    profile = models.JSONField(default=dict, blank=True)         # per-column stats, preview, issues
    status = models.CharField(max_length=20, choices=STATUSES, default="validated")
    storage_path = models.CharField(max_length=300, blank=True, default="")   # HDFS path or local staging path
    storage_backend = models.CharField(max_length=20, blank=True, default="")  # hdfs | local-staging
    description = models.TextField(blank=True, default="")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.name


class SensorReading(models.Model):
    """One observation from a station/sensor. `source` says whether it is real or sample data."""
    SOURCES = [("live", "Live observation (Open-Meteo)"), ("upload", "Uploaded dataset"),
               ("api", "Real-time ingestion API"), ("sample", "Sample data (synthetic)")]
    station = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True, default="")
    region = models.CharField(max_length=50, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(db_index=True)
    temperature = models.FloatField(null=True, blank=True)    # °C
    rainfall = models.FloatField(null=True, blank=True)       # mm
    humidity = models.FloatField(null=True, blank=True)       # %
    co2 = models.FloatField(null=True, blank=True)            # ppm
    source = models.CharField(max_length=10, choices=SOURCES, default="sample", db_index=True)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["region", "timestamp"]), models.Index(fields=["country", "timestamp"])]

    def __str__(self):
        return f"{self.station} @ {self.timestamp:%Y-%m-%d}"


# ---------------------------------------------------------------------------
# Processing + machine learning runs
# ---------------------------------------------------------------------------
class ProcessingJob(models.Model):
    JOB_TYPES = [
        ("yearly_temperature", "Yearly average temperature anomaly (MapReduce)"),
        ("disasters_per_year", "Climate disasters per year (MapReduce)"),
        ("hadoop_disasters_per_year", "Climate disasters per year on Hadoop (Hadoop Streaming, needs HDFS)"),
        ("regional_averages", "Regional averages (MapReduce)"),
        ("anomaly_scan", "Anomaly scan"),
        ("correlation", "Correlation analysis"),
        ("train_models", "Train machine-learning models"),
        ("evaluate_alerts", "Evaluate alert rules"),
    ]
    STATUSES = [("queued", "Queued"), ("running", "Running"), ("success", "Success"), ("failed", "Failed")]
    job_type = models.CharField(max_length=40, choices=JOB_TYPES)
    engine = models.CharField(max_length=30, default="local-mapreduce")   # local-mapreduce | hadoop-streaming | python
    status = models.CharField(max_length=10, choices=STATUSES, default="queued")
    input_path = models.CharField(max_length=300, blank=True, default="")
    records_in = models.PositiveIntegerField(default=0)
    records_out = models.PositiveIntegerField(default=0)
    map_tasks = models.PositiveIntegerField(default=0)
    skipped_records = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]


class ModelRun(models.Model):
    """A trained machine-learning model and its real, measured evaluation metrics."""
    name = models.CharField(max_length=100)
    task = models.CharField(max_length=50)            # temperature_trend | rainfall | anomaly
    algorithm = models.CharField(max_length=100)
    data_source = models.CharField(max_length=200)
    is_sample_data = models.BooleanField(default=False)
    n_train = models.PositiveIntegerField(default=0)
    n_test = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict)
    details = models.JSONField(default=dict, blank=True)
    trained_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trained_at"]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
class AlertRule(models.Model):
    VARIABLES = [("temperature", "Temperature (°C)"), ("rainfall", "Rainfall (mm)"),
                 ("humidity", "Humidity (%)"), ("co2", "CO₂ (ppm)"),
                 ("temp_anomaly", "Temperature anomaly vs 1951-1980 (°C)"),
                 ("zscore", "Statistical anomaly (|z-score|)")]
    OPERATORS = [("gt", "above"), ("lt", "below")]
    SEVERITIES = [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")]
    name = models.CharField(max_length=120)
    variable = models.CharField(max_length=20, choices=VARIABLES)
    operator = models.CharField(max_length=2, choices=OPERATORS, default="gt")
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITIES, default="warning")
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def matches(self, value):
        if value is None:
            return False
        return value > self.threshold if self.operator == "gt" else value < self.threshold

    def __str__(self):
        return f"{self.name} ({self.get_variable_display()} {self.get_operator_display()} {self.threshold})"


class Alert(models.Model):
    rule = models.ForeignKey(AlertRule, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=AlertRule.SEVERITIES, default="warning")
    category = models.CharField(max_length=20, default="anomaly")   # temperature | rainfall | anomaly | system
    value = models.FloatField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default="")
    observed_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=200, unique=True, null=True, blank=True)
    read_by = models.ManyToManyField(User, blank=True, related_name="read_alerts")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Reliability: request timing for performance monitoring
# ---------------------------------------------------------------------------
class RequestMetric(models.Model):
    path = models.CharField(max_length=200)
    method = models.CharField(max_length=8)
    status = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)


class ResourceSnapshot(models.Model):
    """CPU / memory / disk utilisation, sampled about once a minute while the app is in use."""
    cpu_pct = models.FloatField()
    mem_pct = models.FloatField()
    disk_pct = models.FloatField()
    process_mb = models.FloatField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)


class MaintenanceNotice(models.Model):
    """Scheduled maintenance announced to all users in advance (banner on every page)."""
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True, default="")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title
