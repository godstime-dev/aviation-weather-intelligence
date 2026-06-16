import logging
from datetime import datetime, timezone
import psycopg2
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
    )

from app import config
from app.database import get_connection

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True
    )
def fetch_weather(lat, lon):
    if not config.OPENWEATHER_API_KEY:
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


# DIMENSION LOOKUPS
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
            raise ValueError(f"Source '{source_name}' not found.")

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
            ON CONFLICT (
                airport_id,
                source_id,
                observed_at
            ) DO NOTHING;
                       """, (
            airport_id,
            source_id,
            observed_at,
            temperature_c,
            wind_speed_knots,
            visibility_km,
            precipitation_inches
            ))

        return cursor.rowcount


def log_start_run(conn, pipeline_name):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO pipeline_runs (pipeline_name, status)
            VALUES (%s, 'RUNNING')
            RETURNING run_id;
                       """, (pipeline_name,))
        return cursor.fetchone()[0]


def log_end_run(conn, run_id, status, processed=0, inserted=0, skipped=0, error_message=None):
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE pipeline_runs
            SET status = %s,
                finished_at = CURRENT_TIMESTAMP,
                records_processed = %s,
                records_inserted = %s,
                records_skipped = %s,
                error_message = %s
            WHERE run_id = %s;
                       """, (
            status,
            processed,
            inserted,
            skipped,
            error_message,
            run_id
            ))


def run_ingestion():
    logger.info("Starting weather ingestion pipeline...")

    conn = None
    run_id = None

    metrics = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0
        }

    try:
        conn = get_connection()

        run_id = log_start_run(conn, "weather_ingestion")
        conn.commit()

        airports = get_airports(conn)
        source_id = get_source_id(conn, "OpenWeather")

        for airport_id, lat, lon in airports:
            metrics["processed"] += 1

            try:
                data = fetch_weather(lat, lon)

                result = insert_weather(conn, airport_id, source_id, data)

                if result == 1:
                    metrics["inserted"] += 1
                else:
                    metrics["skipped"] += 1

                logger.info(f"Processed airport_id={airport_id}")

            except Exception as e:
                metrics["skipped"] += 1
                logger.error(f"Failed airport_id={airport_id}: {e}")

        conn.commit()

        log_end_run(
            conn,
            run_id,
            "SUCCESS",
            metrics["processed"],
            metrics["inserted"],
            metrics["skipped"],
            None
            )
        conn.commit()

        logger.info("Weather ingestion completed successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")

        if conn:
            conn.rollback()

            if run_id:
                try:
                    log_end_run(
                        conn,
                        run_id,
                        "FAILED",
                        metrics["processed"],
                        metrics["inserted"],
                        metrics["skipped"],
                        str(e)
                        )
                    conn.commit()
                except Exception as log_err:
                    logger.critical(f"Failed to log pipeline failure: {log_err}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingestion()