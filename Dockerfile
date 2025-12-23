FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh || true

# Expose port
EXPOSE 9000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entrypoint
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
