CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE weather_readings (
    time TIMESTAMPTZ NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL,
    location_lon DOUBLE PRECISION NOT NULL,
    
    PRIMARY KEY (time, location_lat, location_lon),
    
    altimeter_setting DOUBLE PRECISION,
    pressure_sea_level DOUBLE PRECISION,
    pressure_surface_level DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    temperature_apparent DOUBLE PRECISION,
    dew_point DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    cloud_base DOUBLE PRECISION,
    cloud_ceiling DOUBLE PRECISION,
    cloud_cover DOUBLE PRECISION,
    rain_intensity DOUBLE PRECISION,
    snow_intensity DOUBLE PRECISION,
    sleet_intensity DOUBLE PRECISION,
    freezing_rain_intensity DOUBLE PRECISION,
    precipitation_probability DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    wind_gust DOUBLE PRECISION,
    wind_direction DOUBLE PRECISION,
    visibility DOUBLE PRECISION,
    uv_index DOUBLE PRECISION,
    uv_health_concern DOUBLE PRECISION,
    weather_code INTEGER
);

SELECT create_hypertable('weather_readings', 'time');

CREATE INDEX idx_weather_location ON weather_readings (location_lat, location_lon, time DESC);

ALTER TABLE weather_readings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'location_lat,location_lon'
);

SELECT add_compression_policy('weather_readings', INTERVAL '7 days');