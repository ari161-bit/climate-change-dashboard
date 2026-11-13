# Installation and deployment

## Requirements

- Python 3.11 or newer (pandas 3 needs 3.11+), 64-bit Windows, macOS or Linux
- About 200 MB of free disk space
- Internet access only for ingestion, the live feed and satellite tiles

The brief lists a Hadoop/HDFS/Impala workstation (16 GB RAM, i7). This implementation does not need that: it runs comfortably on a 4 GB machine.

## Run locally

```bash
git clone https://github.com/ari161-bit/climate-change-dashboard.git
cd climate-change-dashboard
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. On the first run `deploy/demo.sqlite3` is copied to `db.sqlite3`, so the user groups, alert thresholds and demo accounts already exist.

## Refresh the data

```bash
python manage.py ingest_climate_data              # everything
python manage.py ingest_climate_data --skip-cities   # skip the per-city NASA POWER download
python manage.py ingest_climate_data --only-cities   # only the city records
```

Each source is fetched independently, so one unreachable source does not stop the others. Afterwards, an administrator can press **Retrain all models now** on the **Models** page to record a fresh run on the new data.

## Other commands

| Command | Purpose |
|---|---|
| `python manage.py seed_climate` | Create groups, thresholds and demo accounts in any database |
| `python manage.py backup_data --keep 7` | Rotating backup zips in `./backups` (schedule with cron / Task Scheduler) |
| `python manage.py test climate --settings=mysite.test_settings` | Run the 37 automated tests |

## Create your own administrator

```bash
python manage.py shell -c "from django.contrib.auth.models import User, Group; u=User.objects.create_user('yourname', password='a-long-passphrase'); u.groups.add(Group.objects.get(name='Administrators'))"
```

## Configuration

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Signs sessions and derives the encryption key. **Set a long random value in production.** Changing it later signs everyone out and makes previously encrypted feedback unreadable |
| `DJANGO_DEBUG` | `True` or `False`; defaults to `True` locally and `False` on Vercel |
| `GOOGLE_MAPS_API_KEY` | Only for the legacy real-estate maps page under `/myshop/` |

A local `.env` file (git-ignored) is read automatically.

## Deploy to Vercel

1. Import the repository in Vercel (framework preset **Other**).
2. Add `DJANGO_SECRET_KEY` under Environment Variables.
3. Deploy. `vercel.json` routes every request to `api/index.py` and bundles the app, the lake and the demo database.

The database is copied to `/tmp` on each server instance, so anything written (feedback, thresholds, uploads, accounts) lives only as long as that instance and is not shared between instances. For a persistent deployment point `DATABASES` at a managed Postgres database; no other change is needed because sessions are signed cookies and the lake is read-only.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `dataset "..." is not in the lake` | Run `python manage.py ingest_climate_data` |
| City table says data is not in the lake | Run `python manage.py ingest_climate_data --only-cities` |
| `manage.py migrate` reports conflicting migrations | The legacy `myshop` app has two leaf migrations. The shipped `deploy/demo.sqlite3` already contains the climate tables, so a fresh clone does not need `migrate`. To change the climate schema, resolve the conflict first with `python manage.py makemigrations --merge myshop` |
| "Form expired" after signing in | A stale tab; reload and try again |
