FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/project

WORKDIR /app

COPY docker/requirements-fastapi.txt /tmp/requirements-fastapi.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements-fastapi.txt

COPY . /app/project

WORKDIR /app/project

EXPOSE 8000

CMD ["uvicorn", "cluster_b.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
