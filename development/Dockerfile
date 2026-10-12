FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY ris/requirements.txt /tmp/requirements.txt
COPY development/constraints.txt /tmp/constraints.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt
COPY ris/ /app/
COPY development/initialize.py /app/development/initialize.py
CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","1","--threads","4","--timeout","300","web.factory:create_clinical_app()"]
