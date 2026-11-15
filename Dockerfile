FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=council.container_settings \
    DJANGO_DATA_DIR=/data \
    DJANGO_DEBUG=0

WORKDIR /app
COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt \
    && groupadd --gid 10001 council \
    && useradd --uid 10001 --gid council --no-create-home council \
    && mkdir -p /data /app/staticfiles \
    && chown -R council:council /data /app

COPY --chown=council:council manage.py ./
COPY --chown=council:council council ./council
COPY --chown=council:council game ./game
COPY --chown=council:council templates ./templates
COPY --chown=council:council static ./static
COPY --chown=council:council docker-entrypoint.py ./

USER council
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=4).read()"]
ENTRYPOINT ["python", "/app/docker-entrypoint.py"]
CMD ["gunicorn", "council.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
