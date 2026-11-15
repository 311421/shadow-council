"""Initialize persistent state, migrate, and hand PID 1 to the application server."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

data = Path(os.environ.get('DJANGO_DATA_DIR', '/data'))
data.mkdir(parents=True, exist_ok=True)
if not os.environ.get('DJANGO_SECRET_KEY'):
    key_file = data / '.secret-key'
    try:
        descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_urlsafe(50))
    os.environ['DJANGO_SECRET_KEY'] = key_file.read_text().strip()
    if not os.environ['DJANGO_SECRET_KEY']:
        raise RuntimeError('The persisted signing key is empty.')

subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'], check=True)
os.execvp(sys.argv[1], sys.argv[1:])
