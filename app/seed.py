import logging
import psycopg2
from app.database import get_connection
logger = logging.getLogger(__name__)


def seed_weather_sources(conn):
    sources = [
        ("Meteostat", "Historical weather observations"),
        ("NOAA", "National Oceanic and Atmospheric Administration"),
        ("METAR", "Aviation weather observations")
        ]

    with conn.cursor() as cursor:
        for name, desc in sources:
            cursor.execute("""
                INSERT INTO dim_weather_source (source_name, description)
                VALUES (%s, %s)
                ON CONFLICT (source_name)
                DO UPDATE SET
                    description = EXCLUDED.description;
            """, (name, desc))

    logger.info("Weather sources seeded successfully.")


def seed_airports(conn):
    airports = [
        (
            "DNAI",
            "QUO",
            "Akwa Ibom International Airport",
            "Uyo",
            "Nigeria",
            5.6052,
            8.0930,
            "65271"
            ),
        (
            "DNAA",
            "ABV",
            "Nnamdi Azikiwe International Airport",
            "Abuja",
            "Nigeria",
            9.0068,
            7.2631,
            "65125",
            ),
        (
            "DNMM",
            "LOS",
            "Murtala Muhammed International Airport",
            "Lagos",
            "Nigeria",
            6.5774,
            3.3211,
            "65201"
            ),
        (
            "KJFK",
            "JFK",
            "John F. Kennedy International Airport",
            "New York",
            "USA",
            40.6413,
            -73.7781,
            "74486"
            ),
        (
            "EGLL",
            "LHR",
            "Heathrow Airport",
            "London",
            "United Kingdom",
            51.4700,
            -0.4543,
            "03772"
            ),
        (
            "OMDB",
            "DXB",
            "Dubai International Airport",
            "Dubai",
            "UAE",
            25.2532,
            55.3657,
            "41194"
            ),
        (
            "EDDF",
            "FRA",
            "Frankfurt Airport",
            "Frankfurt",
            "Germany",
            50.0379,
            8.5622,
            "10637"
            ),
        ]

    with conn.cursor() as cursor:
        for (icao, iata, name, city, country, lat, lon, station_id,) in airports:
            cursor.execute("""
                INSERT INTO dim_airport (
                    airport_icao,
                    iata_code,
                    name,
                    city,
                    country,
                    latitude,
                    longitude,
                    meteostat_station_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (airport_icao)
                DO UPDATE SET
                    iata_code = EXCLUDED.iata_code,
                    name = EXCLUDED.name,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    meteostat_station_id = EXCLUDED.meteostat_station_id;
                    """, (icao, iata, name, city, country, lat, lon, station_id,))

    logger.info("Airports seeded successfully.")


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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()