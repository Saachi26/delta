# One container, for hosts that only run one: the API also serves the built UI.
FROM node:20-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 delta \
    && mkdir -p /data \
    && chown delta:delta /data

COPY --chown=delta:delta backend/ ./
COPY --from=ui --chown=delta:delta /ui/dist ./static

USER delta

# Daily bars change once a day, so a deployed server holds them for hours
# instead of asking upstream every five minutes.
ENV PORT=8080 \
    HISTORY_TTL=21600 \
    LIVE_TTL=120 \
    DATABASE_URL=sqlite:////data/delta.db

EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
