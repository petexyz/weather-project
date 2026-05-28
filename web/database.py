"""
Database operations for web dashboard
"""
import logging
from contextlib import contextmanager
from typing import Optional, Dict, List, Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and queries"""

    def __init__(self, config):
        self.config = config
        self._pool = self._create_pool()

    def _create_pool(self):
        """Create connection pool"""
        try:
            return psycopg2.pool.ThreadedConnectionPool(
                1, 10,
                host=self.config.host,
                dbname=self.config.name,
                user=self.config.user,
                password=self.config.password,
                port=self.config.port
            )
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            return None

    @contextmanager
    def get_connection(self):
        """Get database connection from pool (context manager)"""
        if not self._pool:
            raise RuntimeError("Database pool not available")

        conn = self._pool.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def get_latest_reading(self) -> Optional[Dict[str, Any]]:
        """Get most recent weather reading"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT time, temperature,
                               temperature_apparent AS feels_like, humidity,
                               wind_speed, wind_gust, wind_direction,
                               pressure_sea_level AS pressure, visibility, weather_code,
                               cloud_cover, rain_intensity, snow_intensity,
                               sleet_intensity, freezing_rain_intensity
                        FROM weather_readings
                        ORDER BY time DESC
                        LIMIT 1
                    """)

                    row = cur.fetchone()
                    if not row:
                        return None

                    result = dict(row)
                    result["time"] = result["time"].isoformat()
                    return result
        except Exception as e:
            logger.error(f"Error fetching latest: {e}")
            return None

    def get_24h_history(self) -> List[Dict[str, Any]]:
        """Get last 24 hours"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT time, temperature,
                               temperature_apparent AS feels_like,
                               humidity, wind_speed,
                               pressure_sea_level AS pressure
                        FROM weather_readings
                        WHERE time > NOW() - INTERVAL '24 hours'
                        ORDER BY time ASC
                    """)

                    rows = []
                    for row in cur.fetchall():
                        item = dict(row)
                        item["time"] = item["time"].isoformat()
                        rows.append(item)
                    return rows
        except Exception as e:
            logger.error(f"Error fetching 24h: {e}")
            return []

    def get_7d_summary(self) -> List[Dict[str, Any]]:
        """Get 7-day hourly averages"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            time_bucket('1 hour', time) AS bucket,
                            AVG(temperature) AS avg_temp,
                            MIN(temperature) AS min_temp,
                            MAX(temperature) AS max_temp,
                            AVG(humidity)    AS avg_humidity,
                            AVG(wind_speed)  AS avg_wind
                        FROM weather_readings
                        WHERE time > NOW() - INTERVAL '7 days'
                        GROUP BY bucket
                        ORDER BY bucket ASC
                    """)

                    return [
                        {
                            "time": row["bucket"].isoformat(),
                            "avg_temp": float(row["avg_temp"]) if row["avg_temp"] is not None else None,
                            "min_temp": float(row["min_temp"]) if row["min_temp"] is not None else None,
                            "max_temp": float(row["max_temp"]) if row["max_temp"] is not None else None,
                            "avg_humidity": float(row["avg_humidity"]) if row["avg_humidity"] is not None else None,
                            "avg_wind": float(row["avg_wind"]) if row["avg_wind"] is not None else None,
                        }
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            logger.error(f"Error fetching 7d: {e}")
            return []

    def get_statistics(self) -> Optional[Dict[str, Any]]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT COUNT(*) AS total FROM weather_readings")
                    total = cur.fetchone()["total"]

                    cur.execute("""
                        SELECT MIN(time) AS min_time, MAX(time) AS max_time
                        FROM weather_readings
                    """)
                    span = cur.fetchone()

                    cur.execute("""
                        SELECT AVG(temperature) AS avg_temp,
                               MIN(temperature) AS min_temp,
                               MAX(temperature) AS max_temp,
                               AVG(humidity)    AS avg_humidity,
                               AVG(wind_speed)  AS avg_wind,
                               MAX(wind_gust)   AS max_gust
                        FROM weather_readings
                        WHERE time > NOW() - INTERVAL '24 hours'
                    """)
                    stats = cur.fetchone()

                    return {
                        "total_records": total,
                        "first_record": span["min_time"].isoformat() if span["min_time"] else None,
                        "last_record": span["max_time"].isoformat() if span["max_time"] else None,
                        "last_24h": {
                            "avg_temp": float(stats["avg_temp"]) if stats["avg_temp"] is not None else None,
                            "min_temp": float(stats["min_temp"]) if stats["min_temp"] is not None else None,
                            "max_temp": float(stats["max_temp"]) if stats["max_temp"] is not None else None,
                            "avg_humidity": float(stats["avg_humidity"]) if stats["avg_humidity"] is not None else None,
                            "avg_wind": float(stats["avg_wind"]) if stats["avg_wind"] is not None else None,
                            "max_gust": float(stats["max_gust"]) if stats["max_gust"] is not None else None,
                        }
                    }
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return None

    def close(self):
        """Close all connections"""
        if self._pool:
            self._pool.closeall()
