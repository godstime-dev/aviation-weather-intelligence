-- 1. DIMENSION TABLES

-- Dimension: Airports
CREATE TABLE IF NOT EXISTS dim_airport (
    airport_id SERIAL PRIMARY KEY,
    airport_icao VARCHAR(4) UNIQUE NOT NULL,
    iata_code VARCHAR(3) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    city TEXT,
    country TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Dimension: Weather Data Sources
CREATE TABLE IF NOT EXISTS dim_weather_source (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);


-- 2. FACT TABLES

-- Fact: Weather Observations (METAR / Ground Truth)
CREATE TABLE IF NOT EXISTS fact_weather_observations (
    observation_id SERIAL PRIMARY KEY,

    airport_id INT REFERENCES dim_airport(airport_id),
    source_id INT REFERENCES dim_weather_source(source_id),

    observed_at TIMESTAMP WITH TIME ZONE NOT NULL,

    temperature_c DECIMAL(4,1),
    wind_speed_knots DECIMAL(4,1),
    visibility_miles DECIMAL(4,2),
    precipitation_inches DECIMAL(4,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Fact: Weather Forecasts
CREATE TABLE IF NOT EXISTS fact_weather_forecasts (
    forecast_id SERIAL PRIMARY KEY,

    airport_id INT REFERENCES dim_airport(airport_id),
    source_id INT REFERENCES dim_weather_source(source_id),

    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    forecast_for TIMESTAMP WITH TIME ZONE NOT NULL,

    forecast_temperature_c DECIMAL(4,1),
    forecast_wind_speed_knots DECIMAL(4,1),
    forecast_visibility_miles DECIMAL(4,2),
    forecast_precipitation_inches DECIMAL(4,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Fact: Flight Delays
CREATE TABLE IF NOT EXISTS fact_flight_delays (
    delay_id SERIAL PRIMARY KEY,
    
    airport_id INT REFERENCES dim_airport(airport_id),

    airline TEXT NOT NULL,
    flight_number TEXT NOT NULL,

    scheduled_departure TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_departure TIMESTAMP WITH TIME ZONE,

    delay_minutes INT DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- 3. PERFORMANCE INDEXES

CREATE INDEX IF NOT EXISTS idx_obs_airport_time
    ON fact_weather_observations(airport_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_fc_target_time
    ON fact_weather_forecasts(airport_id, forecast_for);

CREATE INDEX IF NOT EXISTS idx_flights_time
    ON fact_flight_delays(airport_id, scheduled_departure);