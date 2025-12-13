#!/usr/bin/env python3
"""Import historical weather data into database"""

import json
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_batch

# Config
DATA_DIR = os.getenv('DATA_DIR', '/data')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'weather_db')
DB_USER = os.getenv('DB_USER', 'weather_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

def find_weather_files(base_dir):
    """Find all JSON files in YYYYMM/YYYYMMDD directories"""
    files = []
    base_path = Path(base_dir)
    
    for month_dir in sorted(base_path.iterdir()):
        if month_dir.is_dir() and month_dir.name.isdigit() and len(month_dir.name) == 6:
            for day_dir in sorted(month_dir.iterdir()):
                if day_dir.is_dir() and day_dir.name.isdigit() and len(day_dir.name) == 8:
                    for json_file in sorted(day_dir.glob('weather-*.json')):
                        files.append(json_file)
    
    return files

def parse_file(file_path):
    """Parse JSON file and return database rows (may be multiple for timelines)"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        rows = []
        lat = 42.621864  # Default location
        lon = -71.28336
        
        # Structure 1: Timelines API format {data: {timelines: [...]}
        if 'data' in data and 'timelines' in data['data']:
            for timeline in data['data']['timelines']:
                for interval in timeline.get('intervals', []):
                    time_str = interval['startTime']
                    values = interval['values']
                    
                    rows.append((
                        time_str, lat, lon,
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
        
        # Structure 2: Realtime API format {data: {time, values}, location}
        elif 'data' in data and 'time' in data['data']:
            time_str = data['data']['time']
            values = data['data'].get('values', {})
            location = data.get('location', {})
            lat = location.get('lat', lat)
            lon = location.get('lon', lon)
            
            rows.append((
                time_str, lat, lon,
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
        
        return rows if rows else None
        
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def import_batch(conn, rows):
    """Import batch of rows"""
    if not rows:
        return 0
    
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
        execute_batch(cur, sql, rows, page_size=1000)
    
    conn.commit()
    return len(rows)

def main():
    print(f"Scanning {DATA_DIR}...")
    files = find_weather_files(DATA_DIR)
    
    if not files:
        print("No files found!")
        return
    
    print(f"Found {len(files)} files")
    
    # Connect to database
    print("Connecting to database...")
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Process in batches
    batch = []
    imported = 0
    skipped = 0
    
    for i, file_path in enumerate(files, 1):
        rows = parse_file(file_path)
        
        if rows:
            batch.extend(rows)  # Add all rows from this file
        else:
            skipped += 1
        
        # Import when batch is full
        if len(batch) >= 1000:
            imported += import_batch(conn, batch)
            batch = []
            print(f"Progress: {i}/{len(files)} files, {imported} imported")
    
    # Import remaining
    if batch:
        imported += import_batch(conn, batch)
    
    conn.close()
    
    print("\n" + "="*50)
    print(f"Import complete!")
    print(f"Files processed: {len(files)}")
    print(f"Records imported: {imported}")
    print(f"Records skipped: {skipped}")
    print("="*50)

if __name__ == '__main__':
    main()