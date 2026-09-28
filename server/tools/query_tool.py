from typing import Any

from server.db import get_connection


def execute_query(sql: str) -> list[dict[str, Any]]:
    """
    Execute a read-only SQL query and return the results.
    """

    # Basic safety check for V1
    normalized_sql = sql.strip().lower()

    if not normalized_sql.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)

            rows = cursor.fetchall()

            column_names = [
                description.name
                for description in cursor.description
            ]

    return [
        dict(zip(column_names, row))
        for row in rows
    ]