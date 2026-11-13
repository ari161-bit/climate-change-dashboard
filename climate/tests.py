from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from . import analytics, crypto, lake, live, ml, monitor
from .models import AlertThreshold, AuditLog, CustomDataset, Feedback, ModelRun

PASSWORD = 'Zx9!kqpLm2'


def make_user(name, group=None):
    user = User.objects.create_user(name, password=PASSWORD)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


class LakeTests(TestCase):
    def test_manifest_lists_core_datasets(self):
        manifest = lake.load_manifest()
        for name in ('temperature_monthly', 'co2_monthly', 'emissions_country_annual', 'sea_level_annual'):
            self.assertIn(name, manifest)
            self.assertEqual(len(manifest[name]['sha256']), 64)

    def test_partition_pruning_reads_only_requested_years(self):
        df = lake.read_dataset('temperature_monthly', 1990, 1999)
        self.assertEqual(int(df['year'].min()), 1990)
        self.assertEqual(int(df['year'].max()), 1999)

    def test_clean_fills_short_gaps_only(self):
        import pandas as pd
        frame = pd.DataFrame({'year': range(7), 'x': [1.0, None, 3.0, None, None, None, 7.0]})
        cleaned, quality = lake.clean(frame, ['x'], fill_limit=2)
        self.assertEqual(cleaned['x'].iloc[1], 2.0)
        self.assertEqual(quality['gaps_filled'], 1)
        self.assertEqual(int(cleaned['x'].isna().sum()), 3)   # the 3-long gap is left blank


class AnalyticsTests(TestCase):
    def test_dashboard_payload_has_every_section(self):
        data = analytics.dashboard_data(1980, 2020)
        for key in ('kpis', 'alerts', 'annual', 'forecast', 'anomalies', 'regions', 'emissions', 'impacts', 'correlation', 'decades'):
            self.assertIn(key, data)
        self.assertEqual(data['meta']['start'], 1980)
        self.assertEqual(data['annual']['years'][0], 1980)

    def test_year_range_is_clamped_and_swapped(self):
        data = analytics.dashboard_data(2100, 1900)
        self.assertEqual(data['meta']['start'], 1900)
        self.assertEqual(data['meta']['end'], data['meta']['max_year'])

    def test_mapreduce_decades_match_pandas(self):
        mr = analytics.decade_stats(None, None)
        temp = lake.read_dataset('temperature_monthly').dropna(subset=['global_anomaly'])
        expected = temp[temp['year'] // 10 * 10 == 1990]['global_anomaly'].mean()
        self.assertAlmostEqual(mr[1990]['global'], expected, places=9)

    def test_alert_levels(self):
        kpis = {'latest_year': 2025, 'latest_year_anomaly': 1.6, 'latest_month_label': 'Oct 2025', 'latest_month_anomaly': 0.5,
                'co2_latest': 421.0, 'co2_latest_label': 'Sep 2025', 'warming_rate_per_decade': 0.2, 'sea_level_rate': None}
        limits = {'annual_anomaly': 1.0, 'monthly_anomaly': 1.5, 'co2_level': 420, 'warming_rate': 0.25}
        alerts = {a['key']: a for a in analytics.evaluate_alerts(kpis, limits)}
        self.assertEqual(alerts['annual_anomaly']['severity'], 'critical')
        self.assertEqual(alerts['co2_level']['severity'], 'warning')
        self.assertEqual(alerts['monthly_anomaly']['severity'], 'ok')


class ModelTests(TestCase):
    def test_trend_model_selects_by_backtest(self):
        model = ml.trend_model(ml.annual_temperature()['global_anomaly'])
        self.assertEqual(model['best'], min(model['scores'], key=model['scores'].get))
        self.assertEqual(int(model['future'][-1]), ml.FORECAST_END)

    def test_anomaly_model_flags_recent_years(self):
        flagged = ml.anomaly_model(ml.annual_temperature()['global_anomaly'])['flagged']
        self.assertIn(2024, flagged.index)

    def test_regime_model_orders_clusters_cool_to_hot(self):
        summary = ml.regime_model()['summary']
        self.assertEqual(summary[0]['regime'], 'Cool baseline')
        self.assertLess(summary[0]['mean_anomaly'], summary[-1]['mean_anomaly'])

    def test_correlation_matrix_is_symmetric(self):
        corr = ml.correlation_model()
        n = len(corr['labels'])
        for i in range(n):
            self.assertEqual(corr['matrix'][i][i], 1.0)
            for j in range(n):
                self.assertEqual(corr['matrix'][i][j], corr['matrix'][j][i])

    def test_train_all_records_runs(self):
        runs = ml.train_all('tester')
        self.assertEqual(ModelRun.objects.count(), len(runs))
        self.assertEqual(runs[0].triggered_by, 'tester')


class TrendAnalyzerTests(TestCase):
    def test_reproduces_the_known_regional_series(self):
        result = analytics.trend_analysis('imf_forest_carbon', 'Advanced Economies', 'Carbon stocks in forests', 2035)
        self.assertEqual(result['kpis']['recent10'], 57863.19)
        self.assertGreater(result['kpis']['r2'], 0.98)
        self.assertEqual(result['future'][-1][0], 2035)
        self.assertEqual(len(result['fitted']), len(result['observed']))

    def test_outliers_are_beyond_two_sigma(self):
        result = analytics.trend_analysis('imf_forest_carbon', 'Advanced Economies', 'Carbon stocks in forests', 2035)
        self.assertTrue(all(abs(o['z']) >= 2 for o in result['outliers']))
        self.assertEqual(result['kpis']['outliers'], len(result['outliers']))

    def test_forced_model_and_horizon_are_respected(self):
        result = analytics.trend_analysis('imf_disasters', 'Pakistan', 'Number of Disasters: TOTAL', 2040, 'quadratic')
        self.assertEqual(result['model'], 'quadratic')
        self.assertEqual(result['future'][-1][0], 2040)

    def test_country_groups_are_separated_from_countries(self):
        options = analytics.analyzer_options('imf_forest_carbon', 'Carbon stocks in forests')
        self.assertIn('World', options['groups'])
        self.assertIn('Namibia', options['countries'])      # ISO2 code "NA" must not be read as missing
        self.assertNotIn('Namibia', options['groups'])

    def test_too_little_data_is_a_clean_error(self):
        with self.assertRaises(ValueError):
            analytics.trend_analysis('imf_disasters', 'Nowhere', 'Number of Disasters: TOTAL', 2035)

    def test_endpoints(self):
        self.client.force_login(make_user('ana', 'Analysts'))
        ok = self.client.get(reverse('climate:trends_data'), {'dataset': 'imf_forest_carbon', 'entity': 'World', 'indicator': 'Forest area'})
        self.assertEqual(ok.status_code, 200)
        bad = self.client.get(reverse('climate:trends_data'), {'dataset': 'imf_forest_carbon', 'entity': 'Nowhere', 'indicator': 'Forest area'})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.get(reverse('climate:trends_data'), {'dataset': 'secret'}).status_code, 404)


class CryptoTests(TestCase):
    def test_roundtrip_and_idempotence(self):
        token = crypto.encrypt('secret climate note')
        self.assertTrue(token.startswith('enc::'))
        self.assertNotIn('secret', token)
        self.assertEqual(crypto.decrypt(token), 'secret climate note')
        self.assertEqual(crypto.encrypt(token), token)

    def test_feedback_is_encrypted_in_the_database(self):
        item = Feedback(user=make_user('fb'), subject='s')
        item.message = 'hello'
        item.save()
        raw = Feedback.objects.values_list('message_enc', flat=True).get()
        self.assertNotIn('hello', raw)
        self.assertEqual(Feedback.objects.get().message, 'hello')


class AccessTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', 'Administrators')
        self.analyst = make_user('ana', 'Analysts')

    def test_anonymous_users_are_redirected(self):
        for name in ('dashboard', 'data', 'explorer', 'trends', 'trends_options', 'trends_data', 'live', 'satellite', 'models', 'help', 'feedback', 'admin_panel', 'monitor'):
            response = self.client.get(reverse(f'climate:{name}'))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/login/', response['Location'])

    def test_analyst_can_read_but_not_administer(self):
        self.client.force_login(self.analyst)
        for name in ('dashboard', 'explorer', 'trends', 'live', 'satellite', 'models', 'help', 'feedback'):
            self.assertEqual(self.client.get(reverse(f'climate:{name}')).status_code, 200, name)
        for name in ('admin_panel', 'monitor', 'monitor_data', 'backup'):
            self.assertEqual(self.client.get(reverse(f'climate:{name}')).status_code, 302, name)
        self.assertEqual(self.client.get(reverse('climate:explorer_download', args=['co2_monthly'])).status_code, 302)

    def test_analyst_cannot_retrain(self):
        self.client.force_login(self.analyst)
        self.client.post(reverse('climate:models'))
        self.assertEqual(ModelRun.objects.count(), 0)

    def test_admin_can_retrain_download_and_back_up(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('climate:models'))
        self.assertGreater(ModelRun.objects.count(), 0)
        csv = self.client.get(reverse('climate:explorer_download', args=['co2_monthly']))
        self.assertEqual(csv.status_code, 200)
        self.assertTrue(csv.content.startswith(b'year,month,co2_ppm'))
        self.assertEqual(self.client.get(reverse('climate:backup')).status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='backup').exists())

    def test_login_is_audited_and_open_redirects_are_refused(self):
        response = self.client.post(reverse('climate:login'), {'username': 'ana', 'password': PASSWORD, 'next': 'https://evil.example/'})
        self.assertEqual(response['Location'], reverse('climate:dashboard'))
        self.assertTrue(AuditLog.objects.filter(action='login', user='ana').exists())

    def test_failed_login_is_audited(self):
        self.client.post(reverse('climate:login'), {'username': 'ana', 'password': 'wrong'})
        self.assertTrue(AuditLog.objects.filter(action='login_failed').exists())

    def test_logout_requires_post(self):
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse('climate:logout')).status_code, 405)

    def test_signup_creates_analyst(self):
        response = self.client.post(reverse('climate:signup'), {'username': 'newbie', 'password': PASSWORD, 'confirm': PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(username='newbie').groups.filter(name='Analysts').exists())

    def test_signup_rejects_weak_or_mismatched_passwords(self):
        self.client.post(reverse('climate:signup'), {'username': 'weak', 'password': '12345678', 'confirm': '12345678'})
        self.client.post(reverse('climate:signup'), {'username': 'mis', 'password': PASSWORD, 'confirm': 'different'})
        self.assertFalse(User.objects.filter(username__in=['weak', 'mis']).exists())

    def test_csrf_failure_redirects_to_login(self):
        strict = Client(enforce_csrf_checks=True)
        response = strict.post(reverse('climate:login'), {'username': 'ana', 'password': 'x'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('climate:login'))


class AdminToolsTests(TestCase):
    def setUp(self):
        self.admin = make_user('boss', 'Administrators')
        self.analyst = make_user('ana', 'Analysts')
        self.client.force_login(self.admin)

    def test_threshold_validation(self):
        self.client.get(reverse('climate:admin_panel'))
        self.client.post(reverse('climate:admin_panel'), {'action': 'thresholds', 'th_annual_anomaly': '-3', 'th_co2_level': 'abc', 'th_warming_rate': '0.4'})
        self.assertNotEqual(AlertThreshold.objects.get(key='annual_anomaly').value, -3)
        self.assertEqual(AlertThreshold.objects.get(key='warming_rate').value, 0.4)

    def test_csv_upload_and_visibility(self):
        csv = b'year,value\n2000,1\n2001,2\n2002,3.5\n2003,4\n'
        self.client.post(reverse('climate:admin_panel'), {'action': 'upload', 'title': 'My series', 'visibility': 'admins',
                                                           'file': SimpleUploadedFile('s.csv', csv)})
        self.assertEqual(CustomDataset.objects.get().points[0], [2000, 1.0])
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(reverse('climate:explorer_data', args=['custom:my-series'])).status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('climate:explorer_data', args=['custom:my-series'])).status_code, 200)

    def test_bad_upload_is_rejected_cleanly(self):
        self.client.post(reverse('climate:admin_panel'), {'action': 'upload', 'title': 'Bad', 'file': SimpleUploadedFile('b.csv', b'a,b\nx,y\n')})
        self.assertEqual(CustomDataset.objects.count(), 0)

    def test_dataset_endpoint_404_for_unknown(self):
        self.assertEqual(self.client.get(reverse('climate:explorer_data', args=['nope'])).status_code, 404)

    def test_feedback_round_trip(self):
        self.client.force_login(self.analyst)
        self.client.post(reverse('climate:feedback'), {'category': 'bug', 'subject': 'Chart', 'message': 'broken'})
        item = Feedback.objects.get()
        self.client.force_login(self.admin)
        self.client.post(reverse('climate:admin_panel'), {'action': 'respond', 'feedback_id': item.id, 'response': 'fixed', 'resolve': '1'})
        item.refresh_from_db()
        self.assertEqual((item.response, item.status), ('fixed', 'resolved'))


class LiveAndMonitorTests(TestCase):
    def test_live_alert_rules(self):
        rows = [{'city': 'A', 'temp': 41.0, 'pm25': 10}, {'city': 'B', 'temp': 20, 'pm25': 80}, {'city': 'C', 'temp': 20, 'pm25': 5}]
        alerts = live.live_alerts(rows, {'live_heat': 35, 'live_pm25': 35})
        self.assertEqual({(a['city'], a['kind']) for a in alerts}, {('A', 'Heat'), ('B', 'Air quality (PM2.5)')})
        self.assertEqual([a for a in alerts if a['city'] == 'B'][0]['severity'], 'critical')

    def test_monitor_records_requests_and_stages(self):
        before = monitor.snapshot()['requests']
        monitor.record_request('GET', '/x/', 200, 12.5)
        with monitor.stage('unit-test-stage'):
            pass
        snap = monitor.snapshot()
        self.assertEqual(snap['requests'], before + 1)
        self.assertIn('unit-test-stage', [s['name'] for s in snap['stages']])
