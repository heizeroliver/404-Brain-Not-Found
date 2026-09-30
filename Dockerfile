# Kate Foresight: one container for API + frontend (Cloud Run).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_ENV=production FRONTEND_DIR=/srv/frontend

WORKDIR /srv/backend
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY backend/ ./
COPY frontend/ /srv/frontend/

# run as an unprivileged user; the decision log is the only runtime write
RUN useradd --system --uid 10001 app && chown -R app /srv
USER app

EXPOSE 8080
# JWT_SECRET, DEMO_PASSWORD and ADMIN_PASSWORD come from the Cloud Run service config, never from the image.
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
