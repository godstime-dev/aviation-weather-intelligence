import logging
import psycopg2
from app.database import get_connection
logger = logging.getLogger(__name__)

def run_health_check():
    conn = None
    
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
        if result[0] == 1:
            logger.info("Database health check passed.")
            return True
        logger.error("Database health check returned an unexpected result.")
        return False
    except psycopg2.Error as error:
        logger.error(f"Database health check failed: {error}")
        return False
    finally:
        if conn:
            conn.close()