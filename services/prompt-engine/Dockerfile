FROM python:3.11-slim
WORKDIR /var/task
COPY common/layers /opt/layers
RUN find /opt/layers -name requirements.txt -exec pip install --no-cache-dir -r {} +
COPY services/prompt-engine /var/task
CMD ["python", "prompt-engine-lambda/app.py"]
