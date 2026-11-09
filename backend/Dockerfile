FROM python:3.10-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.lock .
RUN python -m pip wheel --wheel-dir /wheels -r requirements.lock

FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/rag/.local/bin:${PATH}"

RUN groupadd --system rag && useradd --system --gid rag --create-home rag

COPY --from=builder /wheels /wheels
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.lock \
    && rm -rf /wheels /tmp/requirements.lock

WORKDIR /app
COPY --chown=rag:rag pyproject.toml alembic.ini ./
COPY --chown=rag:rag alembic ./alembic
COPY --chown=rag:rag app ./app

USER rag
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)"

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
