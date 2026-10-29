FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    FLASK_HOST=0.0.0.0 \
    PORT=8009 \
    USE_DEV_SERVER=0 \
    DATABASE_URL=sqlite:////opt/dashboard/instance/facturacion.db

WORKDIR /opt/dashboard
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 dashboard \
    && useradd --uid 10001 --gid dashboard --no-create-home dashboard \
    && mkdir instance \
    && chown dashboard:dashboard instance

COPY app/ ./app/
COPY config/ ./config/
COPY docs/ ./docs/
COPY scripts/database_contract.py scripts/migrar_base_datos.py scripts/docker_healthcheck.py ./scripts/
COPY run.py README.md ./

USER 10001:10001
EXPOSE 8009
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python", "scripts/docker_healthcheck.py"]
CMD ["python", "run.py"]
