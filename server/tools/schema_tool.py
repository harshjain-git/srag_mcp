from server.db import get_connection


def get_database_schema() -> dict:
    """
    Dynamically retrieve the database schema from PostgreSQL.

    Returns:
        A dictionary containing tables, columns, data types, and foreign-key relationships.
    """
    schema = {
        "tables": {}
    }

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Get tables and their columns
            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
            """)
            columns = cursor.fetchall()

            for table_name, column_name, data_type, is_nullable in columns:
                if table_name not in schema["tables"]:
                    schema["tables"][table_name] = {
                        "columns": []
                    }

                schema["tables"][table_name]["columns"].append({
                    "name": column_name,
                    "data_type": data_type,
                    "nullable": is_nullable == "YES",
                })

            # Get foreign-key relationships
            cursor.execute("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS referenced_table,
                    ccu.column_name AS referenced_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
                ORDER BY tc.table_name, kcu.column_name;
            """)
            relationships = cursor.fetchall()

            schema["relationships"] = []

            for (
                table_name,
                column_name,
                referenced_table,
                referenced_column,
            ) in relationships:
                schema["relationships"].append({
                    "table": table_name,
                    "column": column_name,
                    "references_table": referenced_table,
                    "references_column": referenced_column,
                })

    return schema
