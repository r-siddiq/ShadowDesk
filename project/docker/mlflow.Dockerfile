FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY docker/requirements-mlflow.txt /tmp/requirements-mlflow.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements-mlflow.txt

RUN mkdir -p /mlflow/artifacts

EXPOSE 5000

CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////mlflow/mlflow.db --default-artifact-root /mlflow/artifacts"]
