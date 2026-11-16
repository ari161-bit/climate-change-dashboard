"""EarthScape test suite.  Run:  python manage.py test climatechanges

Uses a temporary database plus temporary upload/staging folders, and forces
HDFS "offline" so tests never write into a real cluster.
"""
import io
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import alerts, datasources, ingestion, ml, reports
from .mapreduce import run_job, run_mapreduce
from .models import Alert, AlertRule, Customer, Dataset, Feedback, ModelRun, ProcessingJob, SensorReading
from .roles import ADMIN, ANALYST, assign_role, is_admin

TMP = tempfile.mkdtemp(prefix="earthscape_test_")
OFFLINE = {"online": False, "detail": "test: HDFS offline", "files": []}

CSV_OK = (b"station,country,region,date,temperature,rainfall,humidity\n"
          b"Kano,Nigeria,Africa,2025-01-15,31.0,0.5,22\n"
          b"Kano,Nigeria,Africa,2025-02-15,,1.0,20\n"
          b"Kano,Nigeria,Africa,2025-02-15,,1.0,20\n"
          b"Accra,Ghana,Africa,2025-03-15,45.5,80.0,85\n")


def make_user(username, role=ANALYST, password="Str0ng!Pass2026"):
    u = User.objects.create_user(username=username, email=f"{username}@example.com", password=password)
    assign_role(u, role)
    return u


MONGO_OFF = {"URI": "mongodb://127.0.0.1:1", "DB": "earthscape_test", "ENABLED": False}
MONGO_STATUS = {"online": False, "version": None, "db": "earthscape_test", "counts": {}, "detail": "test: disabled"}


@override_settings(MEDIA_ROOT=f"{TMP}/media", HDFS_STAGING_DIR=f"{TMP}/staging", BACKUP_DIR=f"{TMP}/backups",
                   MONGODB=MONGO_OFF)
class EarthScapeTestCase(TestCase):
    """HDFS forced offline and MongoDB writes disabled: tests never touch real services."""
    def setUp(self):
        super().setUp()
        for target, value in (("climatechanges.hadoop.status", OFFLINE), ("climatechanges.mongo.status", MONGO_STATUS)):
            patcher = mock.patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Registration, login, authentication, authorization
# ---------------------------------------------------------------------------
class AuthTests(EarthScapeTestCase):
    def test_registration_creates_user_customer_and_analyst_role(self):
        r = self.client.post(reverse("signup"), {
            "full_name": "Test Analyst", "username": "newbie", "email": "newbie@example.com",
            "password1": "GreenLeaf!2026", "password2": "GreenLeaf!2026"})
        self.assertRedirects(r, reverse("login"))
        u = User.objects.get(username="newbie")
        self.assertTrue(u.groups.filter(name=ANALYST).exists())
        c = Customer.objects.get(user=u)
        self.assertTrue(c.password.startswith("pbkdf2_"), "customer password must be hashed")
        self.assertNotIn("GreenLeaf", u.password)

    def test_registration_rejects_mismatched_and_weak_passwords(self):
        r = self.client.post(reverse("signup"), {"full_name": "X", "username": "bad", "email": "b@example.com",
                                                 "password1": "12345678", "password2": "12345679"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="bad").exists())

    def test_duplicate_email_rejected(self):
        make_user("first")
        r = self.client.post(reverse("signup"), {"full_name": "Y", "username": "second", "email": "first@example.com",
                                                 "password1": "GreenLeaf!2026", "password2": "GreenLeaf!2026"})
        self.assertFalse(User.objects.filter(username="second").exists())
        self.assertContains(r, "already registered")

    def test_login_logout(self):
        make_user("ana")
        r = self.client.post(reverse("login"), {"username": "ana", "password": "Str0ng!Pass2026"})
        self.assertRedirects(r, reverse("console_overview"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("console_overview")).status_code, 200)
        self.client.get(reverse("logout"))
        self.assertEqual(self.client.get(reverse("console_overview")).status_code, 302)

    def test_wrong_password(self):
        make_user("ana")
        r = self.client.post(reverse("login"), {"username": "ana", "password": "nope"})
        self.assertContains(r, "Wrong username or password")

    def test_login_next_cannot_redirect_off_site(self):
        make_user("ana")
        r = self.client.post(reverse("login") + "?next=//evil.example.com/",
                             {"username": "ana", "password": "Str0ng!Pass2026", "next": "//evil.example.com/"})
        self.assertEqual(r["Location"], reverse("console_overview"))

    def test_console_requires_login(self):
        for name in ["console_overview", "console_analytics", "console_data", "console_processing",
                     "console_predictions", "console_anomalies", "console_alerts", "console_reports",
                     "console_support", "console_settings"]:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn(reverse("login"), r["Location"])

    def test_api_requires_auth(self):
        self.assertEqual(self.client.get(reverse("api_summary")).status_code, 401)
        self.assertEqual(self.client.get(reverse("api_alerts_unread")).status_code, 401)

    def test_role_based_access(self):
        analyst, admin = make_user("ana"), make_user("boss", ADMIN)
        self.assertFalse(is_admin(analyst))
        self.assertTrue(is_admin(admin))
        self.client.force_login(analyst)
        self.assertEqual(self.client.get(reverse("console_users")).status_code, 403)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("console_users")).status_code, 200)

    def test_admin_changes_role_and_deactivates(self):
        admin, analyst = make_user("boss", ADMIN), make_user("ana")
        self.client.force_login(admin)
        self.client.post(reverse("console_users"), {"user_id": analyst.id, "action": "role", "role": ADMIN})
        self.assertTrue(is_admin(User.objects.get(pk=analyst.pk)))
        self.client.post(reverse("console_users"), {"user_id": analyst.id, "action": "deactivate"})
        self.assertFalse(User.objects.get(pk=analyst.pk).is_active)

    def test_profile_update_and_password_change(self):
        u = make_user("ana")
        self.client.force_login(u)
        self.client.get(reverse("console_settings"))
        r = self.client.post(reverse("console_settings"), {"action": "profile", "full_name": "Ana Lyst",
                                                           "email": "ana2@example.com", "city": "Abuja"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Customer.objects.get(user=u).city, "Abuja")
        r = self.client.post(reverse("console_settings"), {"action": "password", "old_password": "Str0ng!Pass2026",
                                                           "new_password1": "N3w!GreenPass", "new_password2": "N3w!GreenPass"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.get(pk=u.pk).check_password("N3w!GreenPass"))


# ---------------------------------------------------------------------------
# 2. Ingestion: upload, validation, cleaning, import, storage
# ---------------------------------------------------------------------------
class IngestionTests(EarthScapeTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user("ana")
        self.client.force_login(self.user)

    def upload(self, name, content, kind="station"):
        return self.client.post(reverse("console_data"), {
            "file": SimpleUploadedFile(name, content), "kind": kind, "name": "", "description": ""})

    def test_csv_upload_profiles_missing_and_duplicates(self):
        r = self.upload("stations.csv", CSV_OK)
        ds = Dataset.objects.get()
        self.assertRedirects(r, reverse("console_dataset", args=[ds.pk]))
        self.assertEqual(ds.rows, 4)
        self.assertEqual(ds.missing_values, 2)
        self.assertEqual(ds.duplicate_rows, 1)
        self.assertTrue(ds.profile["importable_as_readings"])
        self.assertEqual(len(ds.profile["preview_rows"]), 4)

    def test_json_upload(self):
        data = json.dumps({"records": [{"station": "A", "date": "2025-01-01", "temperature": 20}]}).encode()
        self.upload("a.json", data)
        self.assertEqual(Dataset.objects.get().file_format, "json")

    def test_rejects_bad_extension_binary_and_empty(self):
        self.upload("evil.exe", b"MZ\x00\x00")
        self.upload("bin.csv", b"\x00\x01\x02binary")
        self.upload("empty.csv", b"")
        self.assertEqual(Dataset.objects.count(), 0)

    @override_settings(MAX_UPLOAD_MB=0)
    def test_rejects_large_file(self):
        self.upload("big.csv", CSV_OK)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_clean_import_store(self):
        self.upload("stations.csv", CSV_OK)
        ds = Dataset.objects.get()
        url = reverse("console_dataset", args=[ds.pk])
        self.client.post(url, {"action": "clean"})
        ds.refresh_from_db()
        self.assertEqual(ds.profile["cleaning"]["rows_after"], 3)       # duplicate removed
        self.assertEqual(ds.profile["cleaning"]["remaining_missing"], 0)  # gaps filled
        AlertRule.objects.create(name="heat", variable="temperature", operator="gt", threshold=40, severity="critical")
        self.client.post(url, {"action": "import"})
        self.assertEqual(SensorReading.objects.filter(source="upload").count(), 3)
        self.assertTrue(Alert.objects.filter(location="Accra").exists())   # 45.5 °C > 40
        self.client.post(url, {"action": "store"})
        ds.refresh_from_db()
        self.assertEqual(ds.storage_backend, "local-staging")             # honest when HDFS is off
        self.assertIn("year=", ds.storage_path)

    def test_downloads_are_protected(self):
        self.upload("stations.csv", CSV_OK)
        ds = Dataset.objects.get()
        url = reverse("console_dataset_download", args=[ds.pk, "original"])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)


class RealtimeApiTests(EarthScapeTestCase):
    def test_ingest_requires_token(self):
        r = self.client.post(reverse("api_ingest"), "{}", content_type="application/json")
        self.assertEqual(r.status_code, 401)

    @override_settings(INGEST_API_TOKEN="t0ken")
    def test_ingest_creates_readings_and_alerts(self):
        AlertRule.objects.create(name="rain", variable="rainfall", operator="gt", threshold=100, severity="warning")
        body = [{"station": "Dakar", "timestamp": "2026-11-01T12:00:00Z", "temperature": 30, "rainfall": 150},
                {"temperature": 10}]                                      # second one is invalid
        r = self.client.post(reverse("api_ingest"), json.dumps(body), content_type="application/json",
                             HTTP_X_API_TOKEN="t0ken")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["created"], 1)
        self.assertEqual(len(r.json()["errors"]), 1)
        self.assertEqual(SensorReading.objects.get().source, "api")
        self.assertEqual(Alert.objects.count(), 1)


# ---------------------------------------------------------------------------
# 3. Processing (MapReduce) and machine learning
# ---------------------------------------------------------------------------
class ProcessingTests(EarthScapeTestCase):
    def test_mapreduce_engine_counts_and_skips_bad_rows(self):
        rows = [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}, {"k": "a", "v": "3"}, {"k": "a", "v": "oops"}]
        mr = run_mapreduce(rows, lambda r: [(r["k"], float(r["v"]))], lambda k, vs: sum(vs), n_tasks=2)
        self.assertEqual(mr.output, {"a": 4.0, "b": 2.0})
        self.assertEqual(mr.skipped, 1)
        self.assertEqual(mr.map_tasks, 2)

    def test_jobs_run_and_are_recorded(self):
        for jt in ("yearly_temperature", "disasters_per_year", "regional_averages", "correlation"):
            job = run_job(jt)
            self.assertEqual(job.status, "success", job.error)
            self.assertGreater(job.records_out, 0)
        job = ProcessingJob.objects.filter(job_type="yearly_temperature").first()
        self.assertIn("2023", job.result["output"])
        self.assertIn("hadoop-streaming", job.result["hadoop_command"])

    def test_unknown_job_fails_cleanly(self):
        self.assertEqual(run_job("nope").status, "failed")


class MLTests(EarthScapeTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sample_data", stdout=io.StringIO())

    def test_temperature_trend_uses_holdout_and_real_metrics(self):
        tt = ml.temperature_trend("World")
        self.assertEqual(tt["n_test"], 10)
        self.assertEqual(len(tt["evaluation"]), 3)
        self.assertIn(tt["best_model"], [e["model"] for e in tt["evaluation"]])
        best = min(tt["evaluation"], key=lambda e: e["RMSE"])
        self.assertEqual(best["model"], tt["best_model"])
        self.assertEqual(tt["future_years"][-1], 2035)
        self.assertGreater(tt["warming_per_decade"], 0)   # the real data shows warming

    def test_rainfall_model_flags_sample_data(self):
        rf = ml.rainfall_model()
        self.assertTrue(rf["ready"])
        self.assertTrue(rf["is_sample_data"])
        self.assertEqual(rf["n_train"] + rf["n_test"], SensorReading.objects.exclude(rainfall=None).count())

    def test_anomalies_and_correlation(self):
        an = ml.anomaly_detection()
        self.assertGreater(an["n_points"], 1000)
        self.assertIsNotNone(an["isolation_forest"])
        corr = ml.correlation_analysis()
        self.assertTrue(-1 <= corr["pairs"][0]["r"] <= 1)
        self.assertIsNotNone(corr["matrix"])

    def test_train_all_records_runs(self):
        runs = ml.train_all()
        self.assertEqual(len(runs), 3)
        self.assertTrue(ModelRun.objects.get(task="rainfall").is_sample_data)
        self.assertFalse(ModelRun.objects.get(task="temperature_trend").is_sample_data)

    def test_sample_rows_are_labelled(self):
        self.assertFalse(SensorReading.objects.exclude(source="sample").exists())
        self.assertEqual(datasources.data_badge({"sample"}), "sample data")
        self.assertEqual(datasources.data_badge({"live"}), "real observations")


# ---------------------------------------------------------------------------
# 4. Alerts, support, reports, dashboard
# ---------------------------------------------------------------------------
class AlertTests(EarthScapeTestCase):
    def test_threshold_rule_dedupes_and_read_status(self):
        u = make_user("ana")
        rule = AlertRule.objects.create(name="heat", variable="temperature", operator="gt", threshold=35)
        from django.utils import timezone
        r = SensorReading.objects.create(station="X", timestamp=timezone.now(), temperature=40, source="api")
        self.assertEqual(alerts.check_reading(r), 1)
        self.assertEqual(alerts.check_reading(r), 0)        # same reading -> no duplicate alert
        self.assertEqual(alerts.unread_for(u).count(), 1)
        self.client.force_login(u)
        self.client.post(reverse("console_alerts"), {"action": "read", "id": Alert.objects.get().id})
        self.assertEqual(alerts.unread_for(u).count(), 0)
        self.assertFalse(rule.matches(None))

    def test_only_admin_can_edit_rules(self):
        self.client.force_login(make_user("ana"))
        self.client.post(reverse("console_alerts"), {"action": "save_rule", "name": "x", "variable": "rainfall",
                                                     "operator": "gt", "threshold": 5, "severity": "info"})
        self.assertEqual(AlertRule.objects.count(), 0)
        self.client.force_login(make_user("boss", ADMIN))
        self.client.post(reverse("console_alerts"), {"action": "save_rule", "name": "x", "variable": "rainfall",
                                                     "operator": "gt", "threshold": 5, "severity": "info", "active": "on"})
        self.assertEqual(AlertRule.objects.count(), 1)

    def test_temp_anomaly_rule_uses_real_data(self):
        AlertRule.objects.create(name="hot country", variable="temp_anomaly", operator="gt", threshold=2.5, severity="critical")
        self.assertGreater(alerts.evaluate_rules(), 0)


class SupportTests(EarthScapeTestCase):
    def test_user_submits_admin_replies_user_sees_status(self):
        ana, boss = make_user("ana"), make_user("boss", ADMIN)
        self.client.force_login(ana)
        self.client.post(reverse("console_support"), {"kind": "issue", "subject": "Map", "message": "Map is blank"})
        fb = Feedback.objects.get()
        self.assertEqual((fb.user, fb.status), (ana, "open"))
        self.client.force_login(make_user("other"))
        self.assertEqual(self.client.get(reverse("console_support_detail", args=[fb.pk])).status_code, 404)
        self.client.force_login(boss)
        self.client.post(reverse("console_support_detail", args=[fb.pk]), {"status": "resolved", "admin_reply": "Fixed"})
        fb.refresh_from_db()
        self.assertEqual((fb.status, fb.resolved, fb.replied_by), ("resolved", True, boss))
        self.client.force_login(ana)
        self.assertContains(self.client.get(reverse("console_support_detail", args=[fb.pk])), "Fixed")


class ReportAndDashboardTests(EarthScapeTestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sample_data", stdout=io.StringIO())

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("ana"))

    def test_landing_page_uses_real_coverage_and_intro_assets(self):
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The future is not a forecast.")
        self.assertContains(response, "cinematic-intro")
        self.assertContains(response, "cinematic-home.css")
        self.assertContains(response, "cinematic-home.js")
        self.assertGreater(response.context["land_country_count"], 0)
        self.assertContains(response, "<b>" + str(response.context["land_country_count"]) + "</b> reporting countries")

    def test_every_report_in_pdf_and_csv(self):
        for kind in reports.REPORTS:
            pdf = self.client.get(reverse("console_reports"), {"kind": kind, "format": "pdf"})
            self.assertEqual(pdf["Content-Type"], "application/pdf")
            self.assertTrue(pdf.content.startswith(b"%PDF-1.4") and pdf.content.rstrip().endswith(b"%%EOF"), kind)
            csv = self.client.get(reverse("console_reports"), {"kind": kind, "format": "csv"})
            self.assertEqual(csv["Content-Type"], "text/csv")
            self.assertIn(b"EarthScape", csv.content)

    def test_dashboard_pages_and_filters(self):
        pages = [("console_overview", {}), ("console_overview", {"region": "Africa", "variable": "rainfall",
                                                                  "start": "2020-01-01", "end": "2022-12-31"}),
                 ("console_analytics", {"fao_country": "Nigeria"}), ("console_predictions", {"country": "Europe"}),
                 ("console_anomalies", {"z": "2"}), ("console_processing", {}), ("console_data", {}),
                 ("console_alerts", {"state": "unread"}), ("console_reports", {"kind": "summary"}),
                 ("console_support", {}), ("console_settings", {})]
        for name, params in pages:
            self.assertEqual(self.client.get(reverse(name), params).status_code, 200, name)

    def test_series_api_filters(self):
        r = self.client.get(reverse("api_series"), {"variable": "humidity", "region": "Europe"})
        self.assertEqual(r.json()["data"], "sample data")
        self.assertTrue(r.json()["months"])
        self.assertEqual(self.client.get(reverse("api_series"), {"variable": "x"}).status_code, 400)

    def test_backup_command(self):
        from .management.commands.backup_earthscape import make_backup
        self.assertTrue(make_backup().name.endswith(".zip.enc"))


# ---------------------------------------------------------------------------
# 5. Non-functional: encryption, backups, health, maintenance, help, BI export
# ---------------------------------------------------------------------------
class NonFunctionalTests(EarthScapeTestCase):
    def setUp(self):
        super().setUp()
        self.admin = make_user("boss", ADMIN)
        self.client.force_login(self.admin)

    def test_uploads_encrypted_at_rest_and_downloads_decrypted(self):
        from . import crypto
        self.client.post(reverse("console_data"), {"file": SimpleUploadedFile("s.csv", CSV_OK), "kind": "station"})
        ds = Dataset.objects.get()
        with ds.file.open("rb") as fh:
            on_disk = fh.read()
        self.assertTrue(crypto.is_encrypted(on_disk))
        self.assertNotIn(b"Kano", on_disk)
        r = self.client.get(reverse("console_dataset_download", args=[ds.pk, "original"]))
        self.assertEqual(r.content, CSV_OK)
        self.client.post(reverse("console_dataset", args=[ds.pk]), {"action": "clean"})
        ds.refresh_from_db()
        with ds.cleaned_file.open("rb") as fh:
            self.assertTrue(crypto.is_encrypted(fh.read()))

    def test_tampered_file_is_rejected(self):
        from . import crypto
        token = bytearray(crypto.encrypt(b"secret climate data"))
        token[-5] ^= 1
        with self.assertRaises(ValueError):
            crypto.decrypt(bytes(token))

    def test_encrypted_backup_and_restore_roundtrip(self):
        from . import crypto
        from .management.commands.backup_earthscape import make_backup
        path = make_backup()
        self.assertTrue(path.name.endswith(".zip.enc"))
        import zipfile
        data = crypto.decrypt(path.read_bytes())
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertTrue(any(n.endswith("Temperature.csv") for n in z.namelist()))

    def test_health_endpoint_for_load_balancer(self):
        self.client.logout()
        r = self.client.get(reverse("api_health"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_maintenance_notice_shown_to_everyone(self):
        from django.utils import timezone
        start = (timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        end = (timezone.now() + timezone.timedelta(days=1, hours=1)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(reverse("console_settings"), {"action": "maintenance", "title": "DB upgrade",
                                                       "message": "20 min", "starts_at": start, "ends_at": end})
        self.client.force_login(make_user("ana"))
        self.assertContains(self.client.get(reverse("console_overview")), "Scheduled maintenance: DB upgrade")
        self.client.logout()
        self.assertContains(self.client.get(reverse("index")), "Scheduled maintenance: DB upgrade")

    def test_analyst_cannot_post_maintenance(self):
        from .models import MaintenanceNotice
        self.client.force_login(make_user("ana"))
        self.client.post(reverse("console_settings"), {"action": "maintenance", "title": "x",
                                                       "starts_at": "2030-01-01T00:00", "ends_at": "2030-01-01T01:00"})
        self.assertFalse(MaintenanceNotice.objects.exists())

    def test_help_center_and_resource_monitoring(self):
        self.assertContains(self.client.get(reverse("console_help")), "Frequently asked questions")
        r = self.client.get(reverse("console_processing"))
        self.assertContains(r, "Resource utilisation")
        self.assertContains(r, "MongoDB document store")

    def test_tableau_extract(self):
        import zipfile
        r = self.client.get(reverse("console_reports"), {"kind": "tableau"})
        self.assertEqual(r["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        for n in ("fact_temperature.csv", "fact_disasters.csv", "fact_readings.csv", "dim_country.csv", "README.txt"):
            self.assertIn(n, names)

    def test_series_api_reports_units(self):
        call_command("seed_sample_data", stdout=io.StringIO())
        r = self.client.get(reverse("api_series"), {"variable": "temperature"})
        self.assertEqual(r.json()["unit"], "degC")
