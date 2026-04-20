FROM python:3.12-slim

WORKDIR /app
COPY oss_provisioner.py .

ENV OSS_HOST=host.docker.internal
ENV OSS_PORT=8069
ENV OSS_INTERVAL=10
ENV OSS_STEP_DELAY=3

CMD ["python", "oss_provisioner.py"]
