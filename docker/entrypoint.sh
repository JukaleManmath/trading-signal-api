#!/bin/bash

echo "Waiting for Postgres to be ready..."
while ! nc -z db 5432; do
  sleep 1
done

echo "Running Alembic migrations..."
cd /app
alembic upgrade head

echo "Starting FastAPI app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
