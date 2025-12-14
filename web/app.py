#!/usr/bin/env python3
"""Weather Dashboard API"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import psycopg2
import os
from datetime import datetime, timedelta

app = FastAPI(title="Weather Dashboard")

# Database config
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'weather_db')
DB_USER = os.getenv('DB_USER', 'weather_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def get_db():
    """Get database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.get("/api/latest")
def get_latest():
    """Get most recent weather reading"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT time, temperature, temperature_apparent, humidity, 
               wind_speed, wind_gust, wind_direction,
               pressure_sea_level, visibility, weather_code,
               cloud_cover, rain_intensity, snow_intensity, 
               sleet_intensity, freezing_rain_intensity
        FROM weather_readings 
        ORDER BY time DESC 
        LIMIT 1
    """)
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return {"error": "No data"}
    
    return {
        "time": row[0].isoformat(),
        "temperature": row[1],
        "feels_like": row[2],
        "humidity": row[3],
        "wind_speed": row[4],
        "wind_gust": row[5],
        "wind_direction": row[6],
        "pressure": row[7],
        "visibility": row[8],
        "weather_code": row[9],
        "cloud_cover": row[10],
        "rain_intensity": row[11],
        "snow_intensity": row[12],
        "sleet_intensity": row[13],
        "freezing_rain_intensity": row[14]
    }

@app.get("/api/history/24h")
def get_24h_history():
    """Get last 24 hours of data"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT time, temperature, temperature_apparent, humidity, wind_speed, pressure_sea_level
        FROM weather_readings 
        WHERE time > NOW() - INTERVAL '24 hours'
        ORDER BY time ASC
    """)
    
    rows = cur.fetchall()
    conn.close()
    
    return {
        "data": [
            {
                "time": row[0].isoformat(),
                "temperature": row[1],
                "feels_like": row[2],
                "humidity": row[3],
                "wind_speed": row[4],
                "pressure": row[5]
            }
            for row in rows
        ]
    }

@app.get("/api/history/7d")
def get_7d_summary():
    """Get 7-day hourly averages"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            time_bucket('1 hour', time) AS hour,
            AVG(temperature) as avg_temp,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            AVG(humidity) as avg_humidity,
            AVG(wind_speed) as avg_wind
        FROM weather_readings 
        WHERE time > NOW() - INTERVAL '7 days'
        GROUP BY hour
        ORDER BY hour ASC
    """)
    
    rows = cur.fetchall()
    conn.close()
    
    return {
        "data": [
            {
                "time": row[0].isoformat(),
                "avg_temp": float(row[1]) if row[1] else None,
                "min_temp": float(row[2]) if row[2] else None,
                "max_temp": float(row[3]) if row[3] else None,
                "avg_humidity": float(row[4]) if row[4] else None,
                "avg_wind": float(row[5]) if row[5] else None
            }
            for row in rows
        ]
    }

@app.get("/api/stats")
def get_stats():
    """Get database statistics"""
    conn = get_db()
    cur = conn.cursor()
    
    # Total records
    cur.execute("SELECT COUNT(*) FROM weather_readings")
    total_records = cur.fetchone()[0]
    
    # Date range
    cur.execute("SELECT MIN(time), MAX(time) FROM weather_readings")
    min_date, max_date = cur.fetchone()
    
    # Recent stats (last 24h)
    cur.execute("""
        SELECT 
            AVG(temperature), MIN(temperature), MAX(temperature),
            AVG(humidity), AVG(wind_speed), MAX(wind_gust)
        FROM weather_readings 
        WHERE time > NOW() - INTERVAL '24 hours'
    """)
    stats_24h = cur.fetchone()
    
    conn.close()
    
    return {
        "total_records": total_records,
        "first_record": min_date.isoformat() if min_date else None,
        "last_record": max_date.isoformat() if max_date else None,
        "last_24h": {
            "avg_temp": float(stats_24h[0]) if stats_24h[0] else None,
            "min_temp": float(stats_24h[1]) if stats_24h[1] else None,
            "max_temp": float(stats_24h[2]) if stats_24h[2] else None,
            "avg_humidity": float(stats_24h[3]) if stats_24h[3] else None,
            "avg_wind": float(stats_24h[4]) if stats_24h[4] else None,
            "max_gust": float(stats_24h[5]) if stats_24h[5] else None
        }
    }

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the dashboard HTML"""
    with open("/app/static/index.html", "r") as f:
        return f.read()

# Serve static files
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)