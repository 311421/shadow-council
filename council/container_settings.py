import os
from pathlib import Path

# Docker exec commands also need the persisted key; they do not inherit the
# environment generated inside the running entrypoint process.
_key_file = Path(os.environ.get('DJANGO_DATA_DIR', '/data')) / '.secret-key'
if not os.environ.get('DJANGO_SECRET_KEY') and _key_file.is_file():
    os.environ['DJANGO_SECRET_KEY'] = _key_file.read_text().strip()

from .settings import *

MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
