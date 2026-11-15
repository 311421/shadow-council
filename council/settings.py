import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('DJANGO_DATA_DIR', str(BASE_DIR)))
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.')
    # Persist the development key so guest cookies survive server restarts.
    key_file = DATA_DIR / '.secret-key'
    try:
        with key_file.open('x') as handle:
            handle.write(secrets.token_urlsafe(50))
    except FileExistsError:
        pass
    SECRET_KEY = key_file.read_text()

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1],testserver').split(',')
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'game']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'council.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request']},
}]
WSGI_APPLICATION = 'council.wsgi.application'
ASGI_APPLICATION = 'council.asgi.application'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3', 'NAME': DATA_DIR / 'db.sqlite3',
    # SQLite has no SELECT FOR UPDATE. IMMEDIATE serializes the short write
    # transactions before reading, preventing lost votes across workers.
    'OPTIONS': {'timeout': 10, 'transaction_mode': 'IMMEDIATE'},
    'TEST': {'NAME': BASE_DIR / 'test-council.sqlite3'},
}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = os.environ.get('DJANGO_COOKIE_SECURE', '0' if DEBUG else '1') == '1'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
USE_TZ = True
