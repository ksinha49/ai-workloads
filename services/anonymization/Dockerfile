FROM python:3.13-slim
WORKDIR /var/task
COPY common/layers /opt/layers
RUN find /opt/layers -name requirements.txt -exec pip install --no-cache-dir -r {} +
COPY services/anonymization /var/task
CMD ["python", "src/mask_text_lambda.py"]
