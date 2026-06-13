import logging
import psycopg2

from app.database import get_connection

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# SEED WEATHER SOURCES
# -----------------------------------------------------------------------------
def seed_weather_sources(conn):
    sources = [
        ("NOAA", "National Oceanic and Atmospheric Administration"),
        ("METAR", "Aviation weather observations"),
        ("OpenWeather", "Commercial weather API"),
        ("WeatherAPI", "Global weather service")
    ]

    with conn.cursor() as cursor:
        for name, desc in sources:
            cursor.execute("""
                INSERT INTO dim_weather_source (source_name, description)
                VALUES (%s, %s)
                ON CONFLICT (source_name) DO NOTHING;
            """, (name, desc))

    logger.info("Weather sources seeded successfully.")


# -----------------------------------------------------------------------------
# SEED AIRPORTS
# -----------------------------------------------------------------------------
def seed_airports(conn):
    airports = [
        ("KJFK", "JFK", "John F. Kennedy International Airport", "New York", "USA", 40.6413, -73.7781),
        ("EGLL", "LHR", "Heathrow Airport", "London", "UK", 51.4700, -0.4543),
        ("DNMM", "LOS", "Murtala Muhammed International Airport", "Lagos", "Nigeria", 6.5774, 3.3211),
        ("DNAI", "QUO", "Akwa Ibom International Airport", "Uyo", "Nigeria", 5.6052, 8.0930),
        ("OMDB", "DXB", "Dubai International Airport", "Dubai", "UAE", 25.2532, 55.3657),
        ("EDDF", "FRA", "Frankfurt Airport", "Frankfurt", "Germany", 50.0379, 8.5622)
    ]

    with conn.cursor() as cursor:
        for icao, iata, name, city, country, lat, lon in airports:
            cursor.execute("""
                INSERT INTO dim_airport (
                    airport_icao,
                    iata_code,
                    name,
                    city,
                    country,
                    latitude,
                    longitude
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (airport_icao) DO NOTHING;
            """, (icao, iata, name, city, country, lat, lon))

    logger.info("Airports seeded successfully.")


# -----------------------------------------------------------------------------
# RUN SEED PIPELINE
# -----------------------------------------------------------------------------
def run_seed():
    logger.info("Starting master data seeding...")

    conn = None

    try:
        conn = get_connection()

        seed_weather_sources(conn)
        seed_airports(conn)

        conn.commit()
        logger.info("Seed completed successfully.")

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Seeding failed: {e}")
        raise

    finally:
        if conn:
            conn.close()


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()