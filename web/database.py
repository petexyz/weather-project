"""
Database operations for web dashboard
"""
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Optional, Dict, List, Any


class DatabaseManager:
    """Manages database connections and queries"""
    
    def __init__(self, config):
        self.config = config
        self._pool = self._create_pool()
    
    def _create_pool(self):
        """Create connection pool"""
        try:
            return psycopg2.pool.SimpleConnectionPool(
                1, 10,
                host=self.config.host,
                dbname=self.config.name,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
        except Exception as e:
            print(f"Failed to create database pool: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get database connection"""
        if not self._pool:
            raise RuntimeError("Database pool not available")
        
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
    
    def get_latest_reading(self) -> Optional[Dict[str, Any]]:
        """Get most recent weather reading"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
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
                    if not row:
                        return None
                    
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
        except Exception as e:
            print(f"Error fetching latest: {e}")
            return None
    
    def get_24h_history(self) -> List[Dict[str, Any]]:
        """Get last 24 hours"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT time, temperature, temperature_apparent, 
                               humidity, wind_speed, pressure_sea_level
                        FROM weather_readings 
                        WHERE time > NOW() - INTERVAL '24 hours'
                        ORDER BY time ASC
                    """)
                    
                    return [
                        {
                            "time": row[0].isoformat(),
                            "temperature": row[1],
                            "feels_like": row[2],
                            "humidity": row[3],
                            "wind_speed": row[4],
                            "pressure": row[5]
                        }
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            print(f"Error fetching 24h: {e}")
            return []
    
    def get_7d_summary(self) -> List[Dict[str, Any]]:
        """Get 7-day hourly averages"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            time_bucket('1 hour', time) AS hour,
                            AVG(temperature), MIN(temperature), MAX(temperature),
                            AVG(humidity), AVG(wind_speed)
                        FROM weather_readings 
                        WHERE time > NOW() - INTERVAL '7 days'
                        GROUP BY hour
                        ORDER BY hour ASC
                    """)
                    
                    return [
                        {
                            "time": row[0].isoformat(),
                            "avg_temp": float(row[1]) if row[1] else None,
                            "min_temp": float(row[2]) if row[2] else None,
                            "max_temp": float(row[3]) if row[3] else None,
                            "avg_humidity": float(row[4]) if row[4] else None,
                            "avg_wind": float(row[5]) if row[5] else None
                        }
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            print(f"Error fetching 7d: {e}")
            return []
    
    def get_statistics(self) -> Optional[Dict[str, Any]]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM weather_readings")
                    total = cur.fetchone()[0]
                    
                    cur.execute("SELECT MIN(time), MAX(time) FROM weather_readings")
                    min_date, max_date = cur.fetchone()
                    
                    cur.execute("""
                        SELECT AVG(temperature), MIN(temperature), MAX(temperature),
                               AVG(humidity), AVG(wind_speed), MAX(wind_gust)
                        FROM weather_readings 
                        WHERE time > NOW() - INTERVAL '24 hours'
                    """)
                    stats = cur.fetchone()
                    
                    return {
                        "total_records": total,
                        "first_record": min_date.isoformat() if min_date else None,
                        "last_record": max_date.isoformat() if max_date else None,
                        "last_24h": {
                            "avg_temp": float(stats[0]) if stats[0] else None,
                            "min_temp": float(stats[1]) if stats[1] else None,
                            "max_temp": float(stats[2]) if stats[2] else None,
                            "avg_humidity": float(stats[3]) if stats[3] else None,
                            "avg_wind": float(stats[4]) if stats[4] else None,
                            "max_gust": float(stats[5]) if stats[5] else None
                        }
                    }
        except Exception as e:
            print(f"Error fetching stats: {e}")
            return None
    
    def close(self):
        """Close all connections"""
        if self._pool:
            self._pool.closeall()