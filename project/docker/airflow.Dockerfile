FROM apache/airflow:3.1.0-python3.12

ENV PYTHONPATH=/opt/airflow/project

USER airflow

COPY docker/requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt

COPY . /opt/airflow/project

WORKDIR /opt/airflow
