import logging
from datetime import datetime, timezone
import psycopg2
import requests
from app import config
from app.database import get_connection
logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def fetch_weather(lat, lon):
    if not config.OPENWEATHER_API_KEY or config.OPENWEATHER_API_KEY == "YOUR_API_KEY":
        raise ValueError("OpenWeather API key is not configured in .env")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": config.OPENWEATHER_API_KEY,
        "units": "metric"
    }

    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_airports(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT airport_id, latitude, longitude
            FROM dim_airport;
        """)
        return cursor.fetchall()


def get_source_id(conn, source_name="OpenWeather"):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT source_id
            FROM dim_weather_source
            WHERE source_name = %s;
        """, (source_name,))

        result = cursor.fetchone()

        if not result:
            raise ValueError(f"Source '{source_name}' not found in dim_weather_source.")

        return result[0]


def insert_weather(conn, airport_id, source_id, data):
    observed_at = datetime.fromtimestamp(data["dt"], tz=timezone.utc)

    temperature_c = data["main"]["temp"]

    wind_speed_knots = data["wind"]["speed"] * 1.94384

    visibility_km = data.get("visibility", 10000) / 1000

    precipitation_inches = 0.0  

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO fact_weather_observations (
                airport_id,
                source_id,
                observed_at,
                temperature_c,
                wind_speed_knots,
                visibility_km,
                precipitation_inches
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (airport_id, source_id, observed_at) DO NOTHING;
        """, (
            airport_id,
            source_id,
            observed_at,
            temperature_c,
            wind_speed_knots,
            visibility_km,
            precipitation_inches
        ))


def run_ingestion():
    logger.info("Starting weather ingestion pipeline...")

    conn = None

    try:
        conn = get_connection()

        airports = get_airports(conn)
        source_id = get_source_id(conn, "OpenWeather")

        for airport_id, lat, lon in airports:
            try:
                data = fetch_weather(lat, lon)
                insert_weather(conn, airport_id, source_id, data)

                logger.info(f"Processed airport_id={airport_id}")

            except Exception as e:
                logger.error(f"Failed for airport_id={airport_id}: {e}")

        conn.commit()
        logger.info("Weather ingestion completed successfully.")

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Pipeline failed: {e}")
        raise

    finally:
        if conn:
            conn.close()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingestion()