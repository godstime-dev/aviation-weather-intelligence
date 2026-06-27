import logging
import pandas as pd
from app.database import get_connection
from app.pipeline_utils import (log_start_run, log_end_run)

logger = logging.getLogger(__name__)

CSV_FILE = "data/T_ONTIME_REPORTING.csv"

def load_dataset():
    logger.info("Loading BTS flight dataset...")

    df = pd.read_csv(CSV_FILE)

    logger.info(f"Loaded {len(df):,} flight records.")

    return df

def extract_airports(df):
    logger.info("Extracting unique airport codes...")

    airports = sorted(
        set(df["ORIGIN"]).union(df["DEST"])
    )

    logger.info(F"Found {len(airports)} unique airports.")

    return airports

def insert_airports(conn, airports):
    logger.info("Inserting airports into dim_airport...")

    inserted = 0

    with conn.cursor() as cursor:
        for airport in airports:
            cursor.execute("""
                           INSERT INTO dim_airport (iata_code)
                           VALUES (%s)
                           ON CONFLICT (iata_code) DO NOTHING;
                           """,(airport,))
            
            inserted += cursor.rowcount

    logger.info(f"Inserted {inserted} new airports.")

    return inserted

def run_ingestion():
    logger.info("Starting airport ingestion pipeline...")

    conn = None
    run_id = None

    metrics = {
        "processed": 0,
        "inserted": 0,
        "skipped": 0
        }
    
    try:
        conn = get_connection()

        run_id = log_start_run(conn, "airport_ingestion")
        conn.commit()

        df = load_dataset()
        airports = extract_airports(df)
        inserted = insert_airports(conn, airports)

        metrics["processed"] = len(airports)
        metrics["inserted"] = inserted
        metrics["skipped"] = len(airports) - inserted

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

        logger.info("Airport ingestion completed successfully.")

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