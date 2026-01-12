# Use official Python 3.11 runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./

# Copy application code
COPY . .

# Install dependencies with pip
RUN pip install --no-cache-dir -e .

# Expose port 8000 for API server
EXPOSE 8000

# Run the development server
CMD ["uvicorn", "station_chief.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
