import psycopg2
from psycopg2 import OperationalError
from app.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
)

def get_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except OperationalError as error:
        raise OperationalError(
            f"Failed to connect to PostgreSQL. "
            f"Original error: {error}"
        ) from error