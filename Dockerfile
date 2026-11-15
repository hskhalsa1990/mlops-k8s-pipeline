# syntax=docker/dockerfile:1

# ---- builder: resolve and install dependencies into an isolated virtualenv ----
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- runtime: minimal, non-root, no build tooling ----
FROM python:3.12-slim

ARG VERSION=dev
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="mlops-classifier" \
      org.opencontainers.image.description="Keras classifier inference API" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/hskhalsa1990/mlops-k8s-pipeline" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${VERSION} \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY predict.py ./
COPY model/ ./model/

# Fixed UID so Kubernetes runAsUser/runAsNonRoot can match it.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/health/live', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "predict:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
