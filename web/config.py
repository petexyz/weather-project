"""
Configuration for web dashboard
"""
import os
from dataclasses import dataclass
from pathlib import Path


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
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            name=os.getenv('DB_NAME', 'weather_db'),
            user=os.getenv('DB_USER', 'weather_user'),
            password=os.getenv('DB_PASSWORD', ''),
            port=int(os.getenv('DB_PORT', '5432'))
        )


@dataclass
class WebConfig:
    """Web server configuration"""
    host: str = "0.0.0.0"
    port: int = 8080
    data_dir: Path = Path('/data')
    
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv('WEB_HOST', '0.0.0.0'),
            port=int(os.getenv('WEB_PORT', '8080')),
            data_dir=Path(os.getenv('DATA_DIR', '/data'))
        )


class Config:
    """Main configuration"""
    
    def __init__(self):
        self.database = DatabaseConfig.from_env()
        self.web = WebConfig.from_env()
    
    @property
    def count_file(self):
        """Path to collection count file"""
        return self.web.data_dir / '.collection_count'