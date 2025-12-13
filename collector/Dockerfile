FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN useradd -m -u 1000 collector && chown -R collector:collector /app
USER collector

CMD ["python", "-u", "weather_collector.py"]