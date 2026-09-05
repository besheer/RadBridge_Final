FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

ARG RADBRIDGE_VERSION=5.46.9
LABEL org.opencontainers.image.title="RadBridge RIS" \
      org.opencontainers.image.version="${RADBRIDGE_VERSION}" \
      org.opencontainers.image.description="RadBridge v5.46.9 fresh schema runtime hardening"

COPY requirements.txt /app/requirements.txt

RUN pip install \
    --no-cache-dir \
    -r /app/requirements.txt

COPY . /app

CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","1","--threads","8","--timeout","300","--access-logfile","-","--error-logfile","-","app:app"]
