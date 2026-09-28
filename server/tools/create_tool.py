from typing import Any

from server.db import get_connection


def get_table_columns(
    cursor,
    table: str,
) -> set[str]:
    """Get valid column names for a table."""

    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table,),
    )

    return {row[0] for row in cursor.fetchall()}


def create_records(
    operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Insert records into one or more existing database tables.

    All operations are executed inside one transaction.
    If any operation fails, all changes are rolled back.
    """

    if not operations:
        raise ValueError("Operations cannot be empty.")

    results = []

    with get_connection() as conn:
        with conn.cursor() as cursor:

            for operation in operations:

                table = operation.get("table")
                records = operation.get("records")

                if not table:
                    raise ValueError("Table name is required.")

                if not records:
                    raise ValueError(
                        f"Records cannot be empty for table '{table}'."
                    )

                # Get actual columns dynamically from PostgreSQL.
                valid_columns = get_table_columns(cursor, table)

                if not valid_columns:
                    raise ValueError(
                        f"Table '{table}' does not exist."
                    )

                for record in records:

                    if not record:
                        raise ValueError(
                            f"Record cannot be empty for table '{table}'."
                        )

                    # Validate supplied columns.
                    invalid_columns = (
                        set(record.keys()) - valid_columns
                    )

                    if invalid_columns:
                        raise ValueError(
                            f"Invalid column(s) for table '{table}': "
                            f"{', '.join(sorted(invalid_columns))}"
                        )

                # All records in this operation must use
                # the same columns.
                columns = list(records[0].keys())

                for record in records:
                    if set(record.keys()) != set(columns):
                        raise ValueError(
                            f"All records for table '{table}' "
                            "must contain the same columns."
                        )

                # Build INSERT dynamically.
                columns_sql = ", ".join(columns)
                placeholders = ", ".join(
                    ["%s"] * len(columns)
                )

                sql = f"""
                    INSERT INTO {table} ({columns_sql})
                    VALUES ({placeholders})
                    RETURNING *
                """

                for record in records:

                    values = [
                        record[column]
                        for column in columns
                    ]

                    cursor.execute(sql, values)

                    row = cursor.fetchone()

                    column_names = [
                        description.name
                        for description in cursor.description
                    ]

                    results.append({
                        "table": table,
                        "record": dict(
                            zip(column_names, row)
                        ),
                    })

        # Commit only after ALL operations succeed.
        conn.commit()

    return results

