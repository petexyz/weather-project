"""
Database operations for weather collector
"""
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Optional, Dict, Any
from logger import get_logger

logger = get_logger()


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, config):
        """
        Initialize database manager
        
        Args:
            config: DatabaseConfig instance
        """
        self.config = config
        self._pool = None
        self._create_pool()
    
    def _create_pool(self):
        """Create connection pool"""
        try:
            self._pool = psycopg2.pool.SimpleConnectionPool(
                1,  # min connections
                5,  # max connections
                host=self.config.host,
                dbname=self.config.name,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
            logger.info(f"✓ Database connection pool created ({self.config.host}:{self.config.port})")
        except Exception as e:
            logger.error(f"✗ Failed to create database pool: {e}")
            self._pool = None
    
    @contextmanager
    def get_connection(self):
        """
        Get database connection from pool (context manager)
        
        Usage:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(...)
        """
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
    
    def insert_weather_reading(self, data: Dict[str, Any]) -> bool:
        """
        Insert weather reading into database
        
        Args:
            data: Weather data dictionary from API
        
        Returns:
            True if successful, False otherwise
        """
        if not self._pool:
            logger.warning("Database pool not available, skipping insert")
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
            
            with self.get_connection() as conn:
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
                    return cur.rowcount > 0
        
        except Exception as e:
            logger.error(f"Database insert failed: {e}")
            return False
    
    def close(self):
        """Close all connections in pool"""
        if self._pool:
            self._pool.closeall()
            logger.info("Database pool closed")