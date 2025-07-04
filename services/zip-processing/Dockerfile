FROM python:3.11-slim
WORKDIR /var/task
COPY common/layers /opt/layers
RUN find /opt/layers -name requirements.txt -exec pip install --no-cache-dir -r {} +
COPY services/zip-processing /var/task
CMD ["python", "zip-creation-lambda/app.py"]
