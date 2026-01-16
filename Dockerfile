FROM python:3.13-slim

WORKDIR /app

COPY hb/requirements.txt hb/requirements.txt
COPY hb/requirements-dev.txt hb/requirements-dev.txt
RUN pip install --no-cache-dir -r hb/requirements.txt -r hb/requirements-dev.txt

COPY . /app

ENV HB_DB_PATH=/app/runs.db
ENV HB_REPORTS_DIR=/app/mvp/reports
ENV HB_METRIC_REGISTRY=/app/metric_registry.yaml
ENV HB_BASELINE_POLICY=/app/baseline_policy.yaml
ENV PYTHONPATH=/app

CMD ["python", "hb/cli.py", "--help"]
