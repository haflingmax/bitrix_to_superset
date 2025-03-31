# Этап 1: Сборка фронтенда
FROM node:22 AS frontend-build
WORKDIR /app

# Устанавливаем Git
RUN apt-get update && apt-get install -y git

# Клонируем репозиторий Superset
RUN git clone https://github.com/apache/superset.git && \
    cd superset && \
    git checkout 4.1.2

# Копируем плагин
COPY plugins/superset-plugin-chart-hello-world /app/superset-plugin-chart-hello-world

# Обновляем package.json фронтенда
RUN sed -i '/"dependencies": {/a \    "superset-plugin-chart-hello-world": "file:../../superset-plugin-chart-hello-world",' \
    /app/superset/superset-frontend/package.json

# Добавляем отсутствующие зависимости
RUN cd /app/superset/superset-frontend && \
    npm install --legacy-peer-deps @react-spring/web global-box currencyformatter.js

# Обновляем MainPreset.js с одинарными кавычками
RUN echo "import { SupersetPluginChartHelloWorld } from '../../../superset-plugin-chart-hello-world/src/index';" > /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js.tmp && \
    sed "/plugins: \[/a \        new SupersetPluginChartHelloWorld().configure({ key: 'hello-world' })," \
    /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js >> /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js.tmp && \
    cp /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js.tmp /home/MainPreset.js.backup && \
    mv /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js.tmp /app/superset/superset-frontend/src/visualizations/presets/MainPreset.js

# Отключаем правило no-unused-vars в .eslintrc.js
RUN sed -i "/rules: {/a\    'no-unused-vars': 'off'," /app/superset/superset-frontend/.eslintrc.js

# Собираем фронтенд
WORKDIR /app/superset/superset-frontend
RUN npm install --legacy-peer-deps
RUN NODE_OPTIONS="--max-old-space-size=8192" npm run build

# Этап 2: Финальный образ
FROM apache/superset:4.1.2
RUN pip install gunicorn psycopg2-binary
USER root
COPY superset_config.py /app/superset_config.py
ENV SUPERSET_CONFIG_PATH=/app/superset_config.py
COPY --from=frontend-build /home /home
COPY --from=frontend-build /app/superset/superset-frontend/dist /app/superset-frontend/dist
USER superset