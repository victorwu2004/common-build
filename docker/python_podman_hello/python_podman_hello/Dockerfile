# ═════════════════════════════════════════════════════════════════════════
# Python Hello World - Container Image
# Works with both Docker and Podman
# ═════════════════════════════════════════════════════════════════════════

# Use official Python slim image (small, secure, official)
FROM python:3.12-slim

# Set metadata (good practice)
LABEL maintainer="you@example.com"
LABEL description="Simple Python hello world app for learning containers"
LABEL version="1.0"

# Set working directory inside container
WORKDIR /app

# Copy requirements first (Docker layer caching optimization)
# If requirements don't change, Docker/Podman skips reinstall
COPY requirements.txt .

# Install dependencies
# --no-cache-dir keeps image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create a non-root user for security (best practice)
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default environment variables (can be overridden at runtime)
ENV NAME="World"
ENV INTERVAL="5"
ENV MESSAGE="Hello from Python in a container!"

# Buffered output can hide logs — disable for real-time viewing
ENV PYTHONUNBUFFERED=1

# Run the app when container starts
CMD ["python", "app.py"]
