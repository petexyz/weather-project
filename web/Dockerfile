FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL Python modules (config, database, app)
COPY config.py database.py app.py ./

# Copy static files
COPY static/ ./static/

# Create non-root user
RUN useradd -m -u 1000 webuser && chown -R webuser:webuser /app
USER webuser

EXPOSE 8080

# Use the refactored app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]