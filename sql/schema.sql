-- DIMENSION TABLES

CREATE TABLE IF NOT EXISTS dim_airport (
    airport_id SERIAL PRIMARY KEY,
    airport_icao VARCHAR(4) UNIQUE,
    iata_code VARCHAR(3) UNIQUE NOT NULL,
    name TEXT,
    city TEXT,
    country TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

CREATE TABLE IF NOT EXISTS dim_weather_source (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
    );


-- FACT TABLES

CREATE TABLE IF NOT EXISTS fact_weather_observations (
    observation_id SERIAL PRIMARY KEY,

    airport_id INT NOT NULL REFERENCES dim_airport(airport_id),
    source_id INT NOT NULL REFERENCES dim_weather_source(source_id),

    observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    temperature_c DECIMAL(4,1),
    wind_speed_knots DECIMAL(4,1),
    visibility_km DECIMAL(5,2),
    precipitation_inches DECIMAL(4,2) DEFAULT 0.0,

    UNIQUE (airport_id, source_id, observed_at)
    );

CREATE TABLE IF NOT EXISTS fact_weather_forecasts (
    forecast_id SERIAL PRIMARY KEY,

    airport_id INT REFERENCES dim_airport(airport_id),
    source_id INT REFERENCES dim_weather_source(source_id),

    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    forecast_for TIMESTAMP WITH TIME ZONE NOT NULL,

    forecast_temperature_c DECIMAL(4,1),
    forecast_wind_speed_knots DECIMAL(4,1),
    forecast_visibility_km DECIMAL(5,2),
    forecast_precipitation_inches DECIMAL(4,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

CREATE TABLE IF NOT EXISTS fact_flight_delays (
    delay_id SERIAL PRIMARY KEY,

    flight_date DATE NOT NULL,

    airline VARCHAR(20) NOT NULL,
    flight_number VARCHAR(20) NOT NULL,

    origin_airport_id INT REFERENCES dim_airport(airport_id),
    dest_airport_id INT REFERENCES dim_airport(airport_id),

    scheduled_departure TIMESTAMP,
    actual_departure TIMESTAMP,

    delay_minutes DECIMAL(8,2) DEFAULT 0,

    cancelled BOOLEAN DEFAULT FALSE,
    cancellation_code VARCHAR(10),

    weather_delay_minutes DECIMAL(8,2) DEFAULT 0,
    nas_delay_minutes DECIMAL(8,2) DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE
        DEFAULT CURRENT_TIMESTAMP
        );

-- INDEXES

CREATE INDEX IF NOT EXISTS idx_obs_airport_time
    ON fact_weather_observations(airport_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_fc_target_time
    ON fact_weather_forecasts(airport_id, forecast_for);

CREATE INDEX IF NOT EXISTS idx_flight_date
    ON fact_flight_delays(flight_date);

CREATE INDEX IF NOT EXISTS idx_origin_dest
    ON fact_flight_delays(origin_airport_id, dest_airport_id);

CREATE INDEX IF NOT EXISTS idx_airline
    ON fact_flight_delays(airline);

-- PIPELINE RUN TRACKING

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL,
    records_processed INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_skipped INT DEFAULT 0,
    error_message TEXT
    );