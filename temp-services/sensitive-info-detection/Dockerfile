FROM python:3.13-slim
WORKDIR /var/task
COPY common/layers /opt/layers
RUN find /opt/layers -name requirements.txt -exec pip install --no-cache-dir -r {} +
COPY services/sensitive-info-detection /var/task
CMD ["python", "detect-sensitive-info-lambda/app.py"]
