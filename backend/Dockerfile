FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# curl is needed for the HEALTHCHECK below.
# The remaining libraries are WeasyPrint's native runtime dependencies
# (Pango/Cairo/GDK-PixBuf/HarfBuzz + shared-mime-info + base fonts).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user. Using a fixed UID/GID makes file ownership predictable
# when bind-mounts are used in development.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --no-create-home --shell /sbin/nologin appuser \
    && mkdir -p /var/adc/vault \
    && chown -R appuser:appuser /app /var/adc/vault
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
