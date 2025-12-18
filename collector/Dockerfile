# collector/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python modules
COPY config.py logger.py database.py weather_collector.py import_historical.py ./

# Create data directory
RUN mkdir -p /data

# Run as non-root user
RUN useradd -m -u 1000 collector && chown -R collector:collector /app /data
USER collector

# Use the refactored collector
CMD ["python", "-u", "weather_collector.py"]