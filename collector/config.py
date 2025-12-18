"""
Centralized configuration management for weather collector
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str
    name: str
    user: str
    password: str
    port: int = 5432
    
    @classmethod
    def from_env(cls):
        """Load database config from environment variables"""
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            name=os.getenv('DB_NAME', 'weather_db'),
            user=os.getenv('DB_USER', 'weather_user'),
            password=os.getenv('DB_PASSWORD', ''),
            port=int(os.getenv('DB_PORT', '5432'))
        )
    
    def connection_string(self):
        """Get psycopg2 connection string"""
        return f"host={self.host} dbname={self.name} user={self.user} password={self.password} port={self.port}"


@dataclass
class WeatherAPIConfig:
    """Weather API configuration"""
    api_key: str
    base_url: str = "https://api.tomorrow.io/v4/weather/realtime"
    timeout: int = 10
    
    @classmethod
    def from_env(cls):
        """Load API config from environment variables"""
        api_key = os.getenv('WEATHER_API_KEY')
        if not api_key:
            raise ValueError("WEATHER_API_KEY environment variable is required")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv('WEATHER_API_URL', cls.base_url),
            timeout=int(os.getenv('TIMEOUT_SECONDS', '10'))
        )


@dataclass
class LocationConfig:
    """Location configuration"""
    latitude: float
    longitude: float
    
    @classmethod
    def from_env(cls):
        """Load location config from environment variables"""
        return cls(
            latitude=float(os.getenv('LOCATION_LAT', '42.621864')),
            longitude=float(os.getenv('LOCATION_LON', '-71.28336'))
        )
    
    def to_string(self):
        """Format as lat,lon string for API"""
        return f"{self.latitude},{self.longitude}"


@dataclass
class CollectorConfig:
    """Collector runtime configuration"""
    data_dir: Path
    collection_interval: int
    retry_delay: int
    max_retries: int
    
    @classmethod
    def from_env(cls):
        """Load collector config from environment variables"""
        return cls(
            data_dir=Path(os.getenv('DATA_DIR', '/data')),
            collection_interval=int(os.getenv('COLLECTION_INTERVAL', '300')),
            retry_delay=int(os.getenv('RETRY_DELAY', '30')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )
    
    @property
    def count_file(self):
        """Path to collection count file"""
        return self.data_dir / '.collection_count'


class Config:
    """Main configuration container"""
    
    def __init__(self):
        self.database = DatabaseConfig.from_env()
        self.api = WeatherAPIConfig.from_env()
        self.location = LocationConfig.from_env()
        self.collector = CollectorConfig.from_env()
    
    def validate(self):
        """Validate all configuration"""
        errors = []
        
        if not self.api.api_key:
            errors.append("Weather API key is missing")
        
        if not self.collector.data_dir.exists():
            try:
                self.collector.data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create data directory: {e}")
        
        if self.collector.collection_interval < 60:
            errors.append("Collection interval must be at least 60 seconds")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    def __repr__(self):
        """String representation (safe - doesn't show passwords)"""
        return (
            f"Config(\n"
            f"  Location: {self.location.latitude}, {self.location.longitude}\n"
            f"  Database: {self.database.host}:{self.database.port}/{self.database.name}\n"
            f"  API: {self.api.base_url}\n"
            f"  Data Dir: {self.collector.data_dir}\n"
            f"  Interval: {self.collector.collection_interval}s\n"
            f")"
        )