FROM python:3.13-slim
WORKDIR /var/task
COPY common/layers /opt/layers
RUN find /opt/layers -name requirements.txt -exec pip install --no-cache-dir -r {} +
COPY services/llm-gateway /var/task
CMD ["python", "src/llm_router_lambda.py"]
