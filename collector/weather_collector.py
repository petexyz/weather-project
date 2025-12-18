#!/usr/bin/env python3
"""
Weather Data Collector - Refactored Version
Cleaner, more maintainable, better error handling
"""

import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
import signal
import sys

from config import Config
from logger import setup_logger, get_logger
from database import DatabaseManager


class CollectionCounter:
    """Manages collection attempt counting"""
    
    def __init__(self, count_file: Path):
        self.count_file = count_file
        self._count = self._load()
    
    def _load(self) -> int:
        """Load count from file"""
        try:
            if self.count_file.exists():
                return int(self.count_file.read_text().strip())
        except Exception:
            pass
        return 0
    
    def increment(self) -> int:
        """Increment and save count"""
        self._count += 1
        try:
            self.count_file.write_text(str(self._count))
        except Exception as e:
            get_logger().warning(f"Could not save count: {e}")
        return self._count
    
    @property
    def current(self) -> int:
        """Get current count"""
        return self._count


class WeatherCollector:
    """Main weather collector class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger()
        self.db = DatabaseManager(config.database)
        self.counter = CollectionCounter(config.collector.count_file)
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("Shutdown signal received, stopping collector...")
        self.running = False
    
    def save_to_file(self, data: dict) -> Path:
        """
        Save weather data to filesystem in YYYYMM/YYYYMMDD/weather-YYYYMMDD-HHMM.json format
        
        Args:
            data: Weather data dictionary
        
        Returns:
            Path to saved file
        
        Raises:
            Exception if save fails
        """
        data_time = datetime.fromisoformat(data['data']['time'].replace('Z', '+00:00'))
        
        # Create directory structure
        month_dir = self.config.collector.data_dir / data_time.strftime('%Y%m')
        day_dir = month_dir / data_time.strftime('%Y%m%d')
        day_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        filename = f"weather-{data_time.strftime('%Y%m%d-%H%M')}.json"
        file_path = day_dir / filename
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return file_path
    
    def fetch_weather_data(self) -> dict:
        """
        Fetch weather data from API
        
        Returns:
            Weather data dictionary
        
        Raises:
            requests.RequestException on API errors
        """
        response = requests.get(
            self.config.api.base_url,
            params={
                'location': self.config.location.to_string(),
                'apikey': self.config.api.api_key
            },
            timeout=self.config.api.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def collect_once(self) -> bool:
        """
        Perform one weather data collection
        
        Returns:
            True if successful, False otherwise
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        
        try:
            # Fetch data
            data = self.fetch_weather_data()
            
            # Save to file
            file_path = self.save_to_file(data)
            
            # Save to database
            db_success = self.db.insert_weather_reading(data)
            
            # Increment counter
            count = self.counter.increment()
            
            # Log result
            status = "✓" if db_success else "⚠️ (file only)"
            self.logger.info(f"[{timestamp}] {status} Saved → {file_path.relative_to(self.config.collector.data_dir)} [{count}]")
            
            return True
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"[{timestamp}] HTTP error: {e.response.status_code} - {e}")
            return False
        
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"[{timestamp}] Connection error: {e}")
            return False
        
        except requests.exceptions.Timeout as e:
            self.logger.error(f"[{timestamp}] Timeout error: {e}")
            return False
        
        except Exception as e:
            self.logger.error(f"[{timestamp}] Unexpected error: {e}", exc_info=True)
            return False
    
    def run(self):
        """Main collection loop"""
        self.logger.info("=" * 60)
        self.logger.info("Weather Data Collector Starting")
        self.logger.info("=" * 60)
        self.logger.info(f"Location: {self.config.location.latitude}, {self.config.location.longitude}")
        self.logger.info(f"Interval: {self.config.collector.collection_interval}s")
        self.logger.info(f"Data dir: {self.config.collector.data_dir}")
        self.logger.info(f"Collections so far: {self.counter.current}")
        self.logger.info("=" * 60)
        
        while self.running:
            self.collect_once()
            
            if self.running:  # Check again before sleeping
                time.sleep(self.config.collector.collection_interval)
        
        # Cleanup
        self.db.close()
        self.logger.info("Weather collector stopped gracefully")


def main():
    """Entry point"""
    try:
        # Load and validate configuration
        config = Config()
        config.validate()
        
        # Setup logging
        log_file = config.collector.data_dir / 'collector.log'
        setup_logger(level='INFO', log_file=log_file)
        
        # Run collector
        collector = WeatherCollector(config)
        collector.run()
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()