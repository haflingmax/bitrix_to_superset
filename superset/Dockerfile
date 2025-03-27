# Этап 1: Сборка плагина
FROM node:16 AS plugin-builder
WORKDIR /app
COPY superset-plugin-chart-d3-tree/package.json ../superset-plugin-chart-d3-tree/package-lock.json ./
RUN npm install
COPY superset-plugin-chart-d3-tree ./
RUN npm run build

# Этап 2: Сборка Superset
FROM apache/superset:latest

RUN pip install gunicorn psycopg2-binary

COPY superset_config.py /app/superset_config.py
ENV SUPERSET_CONFIG_PATH=/app/superset_config.py

USER root
RUN apt-get update && apt-get install -y curl
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && apt-get install -y nodejs

# Копирование скомпилированного плагина
COPY --from=plugin-builder /app/lib /superset-plugin-chart-d3-tree
RUN npm install /superset-plugin-chart-d3-tree --no-save --prefix /usr/local/lib/python3.*/dist-packages/superset-frontend

# Обновление MainPreset.js
RUN sed -i "/this.plugins = \[/a new (require('superset-plugin-chart-d3-tree').default)().configure({ key: 'd3-tree' })," /usr/local/lib/python3.*/dist-packages/superset-frontend/src/visualizations/presets/MainPreset.js

USER superset