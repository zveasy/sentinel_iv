FROM python:3.12-slim

WORKDIR /app

COPY hb/requirements.txt hb/requirements.txt
RUN pip install --no-cache-dir -r hb/requirements.txt

COPY . /app

ENV HB_DB_PATH=/app/runs.db
ENV HB_REPORTS_DIR=/app/mvp/reports
ENV HB_METRIC_REGISTRY=/app/metric_registry.yaml
ENV HB_BASELINE_POLICY=/app/config/thresholds.yaml
ENV PYTHONPATH=/app
ENV HB_UI_HOST=0.0.0.0

EXPOSE 8765
CMD ["python", "hb/cli.py", "ui", "--port", "8765"]
