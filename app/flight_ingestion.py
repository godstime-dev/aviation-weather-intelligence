import logging
from datetime import datetime, timedelta
import pandas as pd
from psycopg2.extras import execute_values
from app.database import get_connection
from app.pipeline_utils import log_start_run, log_end_run

logger = logging.getLogger(__name__)

CSV_FILE = "data/T_ONTIME_REPORTING.csv"

def load_dataset():
    logger.info("Loading BTS flight dataset...")
    df = pd.read_csv(CSV_FILE)
    logger.info(f"Loaded {len(df):,} records")
    return df

def get_airport_map(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
                       SELECT airport_id, iata_code
                       FROM dim_airport;
                       """)
        rows = cursor.fetchall()

    return {iata: airport_id for airport_id, iata in rows}

def convert_time(parsed_date, time_int):
    """Converts BTS format (e.g 700, 2359) into datetime"""
    if pd.isna(time_int):
        return None
    
    time_str = f"{int(time_int):04d}"
    hour = int(time_str[:2])
    minute = int(time_str[2:])

    date = parsed_date

    if hour == 24:
        hour = 0
        date = date + timedelta(days=1)

    return datetime(
        year=date.year,
        month=date.month,
        day=date.day,
        hour=hour,
        minute=minute
        )

def transform(df, airport_map):
    logger.info("Transforming dataset...")

    parsed_dates = pd.to_datetime(df["FL_DATE"], format="mixed", errors="coerce")

    records = []
    missing_airports = 0
    invalid_dates = 0

    for row, parsed_date in zip(df.itertuples(index=False), parsed_dates):
        if pd.isna(parsed_date):
            invalid_dates += 1
            continue

        origin_id = airport_map.get(row.ORIGIN)
        dest_id = airport_map.get(row.DEST)

        if origin_id is None or dest_id is None:
            missing_airports += 1
            continue

        cancelled = bool(row.CANCELLED)

        scheduled_dep = convert_time(parsed_date, row.CRS_DEP_TIME)
        actual_dep = (
            None
            if cancelled
            else convert_time(parsed_date, row.DEP_TIME)
            )
        
        delay_minutes = (
                0
                if cancelled or pd.isna(row.DEP_DELAY)
                else row.DEP_DELAY
                )
        
        cancellation_code = row.CANCELLATION_CODE
        weather_delay = row.WEATHER_DELAY
        nas_delay = row.NAS_DELAY
        
        records.append((
            row.FL_DATE,
            row.OP_UNIQUE_CARRIER,
            str(row.OP_CARRIER_FL_NUM),
            origin_id,
            dest_id,
            scheduled_dep,
            actual_dep,
            delay_minutes,
            cancelled,
            cancellation_code,
            0 if pd.isna(weather_delay) else weather_delay,
            0 if pd.isna(nas_delay) else nas_delay,
            ))
        
    if invalid_dates:
        logger.warning(f"Skipped {invalid_dates:,} rows with invalid flight dates.")
        
    if missing_airports:
        logger.warning(f"Skipped {missing_airports:,} flights because one or both airports were not found.")

    logger.info(f"Transformed {len(records):,} valid records")
    return records

def insert_facts(conn, records):
    logger.info("Inserting fact_flight_delays...")

    with conn.cursor() as cursor:
        execute_values(cursor, """
            INSERT INTO fact_flight_delays (
                flight_date,
                airline,
                flight_number,
                origin_airport_id,
                dest_airport_id,
                scheduled_departure,
                actual_departure,
                delay_minutes,
                cancelled,
                cancellation_code,
                weather_delay_minutes,
                nas_delay_minutes
                )
            VALUES %s
                """, records, page_size=10000)

    return len(records)

def run_ingestion():
    logger.info("Starting flight delay ingestion pipeline...")

    conn = None
    run_id = None

    metrics = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0
        }

    try:
        conn = get_connection()

        run_id = log_start_run(conn, "flight_ingestion")
        conn.commit()

        df = load_dataset()

        airport_map = get_airport_map(conn)

        records = transform(df, airport_map)

        inserted = insert_facts(conn, records)

        metrics["processed"] = len(df)
        metrics["inserted"] = inserted
        metrics["skipped"] = len(df) - inserted

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

        logger.info("Flight ingestion completed successfully.")

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
                    logger.critical(f"Failed to log failure: {log_err}")

        raise

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingestion()