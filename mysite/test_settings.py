"""Settings for `python manage.py test climate --settings=mysite.test_settings`.

The legacy myshop app ships conflicting migrations, so its tables are built straight from its models in tests.
"""
from .settings import *  # noqa: F401,F403

MIGRATION_MODULES = {'myshop': None}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
ALLOWED_HOSTS = ['testserver', 'localhost']
