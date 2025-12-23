from contextlib import contextmanager
from typing import Generator

import mysql.connector
from mysql.connector.connection import MySQLConnection

from config import db_config


def create_connection() -> MySQLConnection:
    return mysql.connector.connect(
        host=db_config.host,
        port=db_config.port,
        user=db_config.user,
        password=db_config.password,
        database=db_config.database,
    )


@contextmanager
def get_connection() -> Generator[MySQLConnection, None, None]:
    
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()