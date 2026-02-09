FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/project

WORKDIR /app

COPY docker/requirements-streamlit.txt /tmp/requirements-streamlit.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements-streamlit.txt

COPY . /app/project

WORKDIR /app/project/dashboard

EXPOSE 80

CMD ["streamlit", "run", "app.py", "--server.port", "80", "--server.address", "0.0.0.0", "--server.headless", "true"]
