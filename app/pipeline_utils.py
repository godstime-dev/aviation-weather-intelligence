def log_start_run(conn, pipeline_name):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO pipeline_runs (pipeline_name, status)
            VALUES (%s, 'RUNNING')
            RETURNING run_id;
        """, (pipeline_name,))
        return cursor.fetchone()[0]


def log_end_run(
        conn,
        run_id,
        status,
        processed=0,
        inserted=0,
        skipped=0,
        error_message=None
        ):
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