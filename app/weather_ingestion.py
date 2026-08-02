import logging
from datetime import datetime

from itertools import islice

import pandas as pd
from meteostat import hourly
from psycopg2.extras import execute_values

from app.database import get_connection
from app.pipeline_utils import log_start_run, log_end_run

logger = logging.getLogger(__name__)

# Historical window matching the BTS flight dataset
START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 1, 31, 23, 59)

# Unit conversions
KMH_TO_KNOTS = 0.539957


def get_source_id(conn):
    """
    Returns the Meteostat source_id.
    """

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT source_id
            FROM dim_weather_source
            WHERE source_name = 'Meteostat';
            """)

        row = cursor.fetchone()

    if row is None:
        raise ValueError(
            "Meteostat weather source not found. Run seed.py first."
            )

    return row[0]


def get_airports(conn):
    """
    Returns every airport configured for Meteostat ingestion.
    Airports without a Meteostat station ID are ignored.
    """

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                airport_id,
                iata_code,
                meteostat_station_id
            FROM dim_airport
            WHERE meteostat_station_id IS NOT NULL
            ORDER BY airport_id;
            """)

        return cursor.fetchall()


def fetch_weather(station_id):
    """
    Downloads hourly historical weather observations
    for a Meteostat station.
    """

    logger.info(f"Fetching historical weather for station {station_id}")

    data = hourly(
        station_id,
        START_DATE,
        END_DATE
        )

    # Allow Meteostat to interpolate missing observations
    data.model = True

    df = data.fetch()

    if df.empty:
        logger.warning(
            f"No historical weather found for station {station_id}"
            )
        return pd.DataFrame()

    # Modern Meteostat mixes strings with Parameter enums.
    # Normalize everything into plain column names.
    df.columns = [
        column.value if hasattr(column, "value") else column
        for column in df.columns
        ]

    df = df.reset_index()

    logger.info(
        f"Retrieved {len(df):,} hourly observations "
        f"for station {station_id}"
        )

    return df


def kmh_to_knots(speed):
    """
    Converts kilometres per hour to knots.
    """

    if pd.isna(speed):
        return None

    return round(speed * KMH_TO_KNOTS, 2)

def normalize_weather(df):
    """
    Normalizes Meteostat hourly observations into the warehouse schema.
    """

    if df.empty:
        return pd.DataFrame()

    weather = pd.DataFrame()

    weather["observed_at"] = df["time"]

    # Temperature
    weather["temperature_c"] = (df["temp"] if "temp" in df.columns else None)


    weather["dew_point_c"] = (df["dwpt"] if "dwpt" in df.columns else None)


    # Humidity
    weather["relative_humidity"] = (df["rhum"] if "rhum" in df.columns else None)


    # Pressure
    weather["pressure_hpa"] = (df["pres"] if "pres" in df.columns else None)


    # Wind
    weather["wind_speed_knots"] = (
        df["wspd"].apply(kmh_to_knots)
        if "wspd" in df.columns
        else None
        )

    weather["wind_direction_deg"] = (df["wdir"] if "wdir" in df.columns else None)


    weather["wind_gust_knots"] = (
        df["wpgt"].apply(kmh_to_knots)
        if "wpgt" in df.columns
        else None
        )

    # Visibility
    # Meteostat rarely provides historical visibility.
    # Store NULL when unavailable instead of inventing values.
    weather["visibility_km"] = (df["vsby"] if "vsby" in df.columns else None)

    # Precipitation
    weather["precipitation_mm"] = (
        df["prcp"].fillna(0)
        if "prcp" in df.columns
        else 0
        )

    # Weather condition code
    weather["weather_code"] = (df["coco"] if "coco" in df.columns else None)

    return weather


def transform_weather(airport_id, source_id, weather_df):
    """
    Converts normalized weather observations into tuples
    ready for bulk insertion.
    """

    weather_df = normalize_weather(weather_df)

    if weather_df.empty:
        return []

    records = []

    for row in weather_df.itertuples(index=False):
        records.append((
            airport_id,
            source_id,
            row.observed_at,
            row.temperature_c,
            row.dew_point_c,
            row.relative_humidity,
            row.pressure_hpa,
            row.wind_speed_knots,
            row.wind_direction_deg,
            row.wind_gust_knots,
            row.visibility_km,
            row.precipitation_mm,
            row.weather_code
            ))

    return records


def chunked(iterable, size):
    """
    Yield successive chunks from an iterable.
    """

    iterator = iter(iterable)

    while True:
        batch = list(islice(iterator, size))

        if not batch:
            break

        yield batch


def insert_weather(conn, records):
    """
    Bulk inserts weather observations into the warehouse.
    Returns the exact number of inserted rows.
    """

    if not records:
        return 0

    inserted = 0

    with conn.cursor() as cursor:

        for batch in chunked(records, 10000):

            execute_values(
                cursor,
                """
                INSERT INTO fact_weather_observations (
                    airport_id,
                    source_id,
                    observed_at,

                    temperature_c,
                    dew_point_c,
                    relative_humidity,
                    pressure_hpa,

                    wind_speed_knots,
                    wind_direction_deg,
                    wind_gust_knots,

                    visibility_km,
                    precipitation_mm,
                    weather_code
                )
                VALUES %s
                ON CONFLICT (
                    airport_id,
                    source_id,
                    observed_at
                    )
                DO NOTHING

                RETURNING observation_id;
                """,
                batch
                )

            inserted += len(cursor.fetchall())

    return inserted


def run_ingestion():

    logger.info("Starting historical weather ingestion pipeline...")

    conn = None
    run_id = None

    metrics = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0
        }

    try:

        conn = get_connection()

        run_id = log_start_run(
            conn,
            "weather_ingestion"
            )

        conn.commit()

        source_id = get_source_id(conn)

        airports = get_airports(conn)

        logger.info(f"Found {len(airports)} airports.")

        for airport_id, iata_code, station_id in airports:

            logger.info(f"Processing {iata_code} ({station_id})...")

            weather_df = fetch_weather(station_id)

            if weather_df.empty:

                logger.warning(f"No weather found for {iata_code}")

                continue

            records = transform_weather(
                airport_id,
                source_id,
                weather_df
                )

            inserted = insert_weather(
                conn,
                records
                )

            processed = len(records)
            skipped = processed - inserted

            metrics["processed"] += processed
            metrics["inserted"] += inserted
            metrics["skipped"] += skipped

            logger.info(
                f"{iata_code}: "
                f"{inserted:,} inserted, "
                f"{skipped:,} skipped"
                )

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

        logger.info("Historical weather ingestion completed successfully.")

        logger.info(f"Processed : {metrics['processed']:,}")

        logger.info(f"Inserted : {metrics['inserted']:,}")

        logger.info(f"Skipped : {metrics['skipped']:,}")

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

                except Exception as log_error:

                    logger.critical(
                        f"Unable to log pipeline failure: {log_error}"
                        )

        raise

    finally:

        if conn:
            conn.close()


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
        )

    run_ingestion()