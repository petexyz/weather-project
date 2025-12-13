#!/usr/bin/env python3
"""Simple weather collector - saves to files and database"""

import os
import requests
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import psycopg2

# Configuration from environment variables
API_KEY = os.getenv('WEATHER_API_KEY')
LAT = os.getenv('LOCATION_LAT', '42.621864')
LON = os.getenv('LOCATION_LON', '-71.28336')
INTERVAL = int(os.getenv('COLLECTION_INTERVAL', '300'))
DATA_DIR = os.getenv('DATA_DIR', '/data')

# Database config
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'weather_db')
DB_USER = os.getenv('DB_USER', 'weather_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def get_db_connection():
    """Connect to database"""
    try:
        return psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        return None

def save_to_file(data):
    """Save to YYYYMM/YYYYMMDD/weather-YYYYMMDD-HHMM.json"""
    try:
        data_time = datetime.fromisoformat(data['data']['time'].replace('Z', '+00:00'))
        
        # Create directories
        month_dir = Path(DATA_DIR) / data_time.strftime('%Y%m')
        day_dir = month_dir / data_time.strftime('%Y%m%d')
        day_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        filename = f"weather-{data_time.strftime('%Y%m%d-%H%M')}.json"
        file_path = day_dir / filename
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return file_path
    except Exception as e:
        print(f"⚠️  File save failed: {e}")
        return None

def save_to_db(conn, data):
    """Insert into database"""
    if not conn:
        return False
    
    try:
        time_str = data['data']['time']
        values = data['data']['values']
        location = data['location']
        
        sql = """
            INSERT INTO weather_readings (
                time, location_lat, location_lon,
                altimeter_setting, pressure_sea_level, pressure_surface_level,
                temperature, temperature_apparent, dew_point, humidity,
                cloud_base, cloud_ceiling, cloud_cover,
                rain_intensity, snow_intensity, sleet_intensity, 
                freezing_rain_intensity, precipitation_probability,
                wind_speed, wind_gust, wind_direction,
                visibility, uv_index, uv_health_concern, weather_code
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            ) ON CONFLICT DO NOTHING;
        """
        
        with conn.cursor() as cur:
            cur.execute(sql, (
                time_str, location['lat'], location['lon'],
                values.get('altimeterSetting'),
                values.get('pressureSeaLevel'),
                values.get('pressureSurfaceLevel'),
                values.get('temperature'),
                values.get('temperatureApparent'),
                values.get('dewPoint'),
                values.get('humidity'),
                values.get('cloudBase'),
                values.get('cloudCeiling'),
                values.get('cloudCover'),
                values.get('rainIntensity'),
                values.get('snowIntensity'),
                values.get('sleetIntensity'),
                values.get('freezingRainIntensity'),
                values.get('precipitationProbability'),
                values.get('windSpeed'),
                values.get('windGust'),
                values.get('windDirection'),
                values.get('visibility'),
                values.get('uvIndex'),
                values.get('uvHealthConcern'),
                values.get('weatherCode')
            ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️  Database insert failed: {e}")
        conn.rollback()
        return False

def main():
    print("Weather Collector Starting...")
    print(f"Location: {LAT}, {LON}")
    print(f"Interval: {INTERVAL}s")
    print(f"Data dir: {DATA_DIR}")
    
    # Connect to database
    db_conn = get_db_connection()
    if db_conn:
        print("✓ Database connected")
    else:
        print("⚠️  Running in file-only mode")
    
    url = "https://api.tomorrow.io/v4/weather/realtime"
    
    count = 0
    while True:
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            
            # Fetch weather data
            response = requests.get(url, params={
                'location': f"{LAT},{LON}",
                'apikey': API_KEY
            }, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Save to file
            file_path = save_to_file(data)
            
            # Save to database
            db_ok = save_to_db(db_conn, data)
            
            count += 1
            status = "✓" if db_ok else "⚠️"
            print(f"[{timestamp}] {status} Saved → {file_path} [{count}]")
            
        except Exception as e:
            print(f"[{timestamp}] ❌ Error: {e}")
        
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()
