FROM apache/superset:latest

RUN pip install gunicorn psycopg2-binary

COPY superset_config.py /app/superset_config.py
ENV SUPERSET_CONFIG_PATH=/app/superset_config.py