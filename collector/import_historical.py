#!/usr/bin/env python3
"""
Historical Weather Data Importer - Refactored
Imports existing JSON files into database with progress tracking
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional
import sys
from datetime import datetime

from config import Config
from logger import setup_logger, get_logger
from database import DatabaseManager


class WeatherFileParser:
    """Parses various weather JSON file formats"""

    def __init__(self, default_lat: float, default_lon: float):
        # Used for the timeline format, which carries no location of its own
        self.default_lat = default_lat
        self.default_lon = default_lon

    @staticmethod
    def _build_row(time_str: str, lat: float, lon: float, values: dict) -> Tuple:
        """Build a database row tuple from a values dict (column order matches INSERT)"""
        return (
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
        )

    def parse_realtime_format(self, data: dict) -> Optional[Tuple]:
        """Parse realtime API format: {data: {time, values}, location}"""
        try:
            location = data['location']
            return self._build_row(
                data['data']['time'],
                location['lat'], location['lon'],
                data['data']['values']
            )
        except (KeyError, TypeError):
            return None

    def parse_timeline_format(self, data: dict) -> List[Tuple]:
        """Parse timeline API format: {data: {timelines: [...]}}"""
        rows = []
        try:
            for timeline in data['data']['timelines']:
                for interval in timeline.get('intervals', []):
                    rows.append(self._build_row(
                        interval['startTime'],
                        self.default_lat, self.default_lon,
                        interval['values']
                    ))
        except (KeyError, TypeError):
            pass

        return rows

    def parse_file(self, file_path: Path) -> List[Tuple]:
        """
        Parse any weather JSON file format

        Returns:
            List of database rows (may be empty if parse fails)
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Try realtime format first
            row = self.parse_realtime_format(data)
            if row:
                return [row]

            # Try timeline format
            rows = self.parse_timeline_format(data)
            if rows:
                return rows

            return []

        except json.JSONDecodeError:
            return []
        except Exception:
            return []


class FileFinder:
    """Finds weather files in directory structure"""
    
    @staticmethod
    def find_files(base_dir: Path) -> List[Path]:
        """
        Find all weather JSON files in YYYYMM/YYYYMMDD directories
        
        Args:
            base_dir: Base data directory
        
        Returns:
            Sorted list of file paths
        """
        files = []
        
        # Look for YYYYMM directories
        for month_dir in sorted(base_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            if not (month_dir.name.isdigit() and len(month_dir.name) == 6):
                continue
            
            # Look for YYYYMMDD subdirectories
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                if not (day_dir.name.isdigit() and len(day_dir.name) == 8):
                    continue
                
                # Find all weather-*.json files
                for json_file in sorted(day_dir.glob('weather-*.json')):
                    files.append(json_file)
        
        return files


class HistoricalImporter:
    """Imports historical weather data"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger()
        self.db = DatabaseManager(config.database)
        self.parser = WeatherFileParser(
            config.location.latitude,
            config.location.longitude
        )
        self.finder = FileFinder()
    
    def import_batch(self, rows: List[Tuple]) -> int:
        """Import a batch of rows"""
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
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    from psycopg2.extras import execute_batch
                    execute_batch(cur, sql, rows, page_size=1000)
                    conn.commit()
            return len(rows)
        except Exception as e:
            self.logger.error(f"Batch import failed: {e}")
            return 0
    
    def run(self):
        """Main import process"""
        self.logger.info("=" * 60)
        self.logger.info("Historical Data Import Starting")
        self.logger.info("=" * 60)
        self.logger.info(f"Scanning: {self.config.collector.data_dir}")
        
        # Find files
        files = self.finder.find_files(self.config.collector.data_dir)
        
        if not files:
            self.logger.warning("No files found!")
            return
        
        self.logger.info(f"Found {len(files):,} files to import")
        self.logger.info("=" * 60)
        
        # Process files
        batch = []
        imported = 0
        skipped = 0
        batch_size = 1000
        
        start_time = datetime.now()
        
        for i, file_path in enumerate(files, 1):
            rows = self.parser.parse_file(file_path)
            
            if rows:
                batch.extend(rows)
            else:
                skipped += 1
            
            # Import when batch is full
            if len(batch) >= batch_size:
                imported += self.import_batch(batch)
                batch = []
                
                # Progress update
                progress = (i / len(files)) * 100
                self.logger.info(
                    f"Progress: {i:,}/{len(files):,} files ({progress:.1f}%) | "
                    f"{imported:,} imported | {skipped:,} skipped"
                )
        
        # Import remaining
        if batch:
            imported += self.import_batch(batch)
        
        elapsed = datetime.now() - start_time
        
        # Summary
        self.logger.info("=" * 60)
        self.logger.info("Import Complete!")
        self.logger.info(f"Files processed: {len(files):,}")
        self.logger.info(f"Records imported: {imported:,}")
        self.logger.info(f"Records skipped: {skipped:,}")
        self.logger.info(f"Time elapsed: {elapsed}")
        self.logger.info(f"Rate: {len(files) / elapsed.total_seconds():.1f} files/sec")
        self.logger.info("=" * 60)


def main():
    """Entry point"""
    try:
        config = Config()
        config.validate()
        
        # Setup logging
        setup_logger(level='INFO')
        
        # Run import
        importer = HistoricalImporter(config)
        importer.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()