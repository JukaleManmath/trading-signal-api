# Dockerfile at root of market-data-service/
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app /app
COPY scripts/ ./scripts/

# Copy alembic config and migration scripts
COPY alembic.ini ./alembic.ini
COPY alembic-migrations ./alembic-migrations

# Copy entrypoint script from docker/ folder
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set entrypoint
CMD ["/app/entrypoint.sh"]
