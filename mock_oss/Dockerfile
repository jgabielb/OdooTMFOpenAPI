FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY oss_simulator.py .

ENV ODOO_BASE_URL=http://host.docker.internal:8069
ENV ODOO_API_KEY=
ENV POLL_INTERVAL=15
ENV STEP_DELAY=5
ENV DRY_RUN=false
ENV LOG_LEVEL=INFO

CMD ["python", "-u", "oss_simulator.py"]
