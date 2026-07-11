"""Repair dimension set tables/FKs for tenant schemas with schema drift."""


def _table_in_current_schema(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = %s
        """,
        [table],
    )
    return cursor.fetchone() is not None


def repair_dimensionsetentry_fks(schema_editor) -> None:
    """
    Repoint dimension_dimensionsetentry FKs that incorrectly reference public.dimension_*.
    """
    cursor = schema_editor.connection.cursor()
    qn = schema_editor.connection.ops.quote_name

    if not _table_in_current_schema(cursor, "dimension_dimensionsetentry"):
        return
    if not _table_in_current_schema(cursor, "dimension_dimension"):
        return
    if not _table_in_current_schema(cursor, "dimension_dimensionvalue"):
        return

    cursor.execute(
        """
        SELECT con.conname,
               a.attname AS column_name,
               rc.relname AS ref_table
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        JOIN pg_class rc ON rc.oid = con.confrelid
        JOIN pg_namespace rn ON rn.oid = rc.relnamespace
        JOIN pg_attribute a
          ON a.attrelid = rel.oid
         AND a.attnum = ANY(con.conkey)
         AND NOT a.attisdropped
        WHERE con.contype = 'f'
          AND ns.nspname = current_schema()
          AND rel.relname = 'dimension_dimensionsetentry'
          AND rn.nspname = 'public'
          AND rc.relname IN ('dimension_dimension', 'dimension_dimensionvalue')
        """
    )
    for conname, column_name, ref_table in cursor.fetchall():
        cursor.execute(
            f"""
            ALTER TABLE {qn("dimension_dimensionsetentry")}
            DROP CONSTRAINT IF EXISTS {qn(conname)}
            """
        )
        cursor.execute(
            f"""
            ALTER TABLE {qn("dimension_dimensionsetentry")}
            ADD CONSTRAINT {qn(conname)}
            FOREIGN KEY ({qn(column_name)})
            REFERENCES {qn(ref_table)} (id)
            DEFERRABLE INITIALLY DEFERRED
            """
        )


def ensure_dimensionset_tables(apps, schema_editor) -> None:
    """
    Create dimension_dimensionset / dimension_dimensionsetentry in the tenant schema
    when migration 0004 was recorded but tables landed in public only.
    """
    cursor = schema_editor.connection.cursor()

    if _table_in_current_schema(cursor, "dimension_dimensionset"):
        repair_dimensionsetentry_fks(schema_editor)
        return

    DimensionSet = apps.get_model("dimension", "DimensionSet")
    DimensionSetEntry = apps.get_model("dimension", "DimensionSetEntry")
    schema_editor.create_model(DimensionSet)
    schema_editor.create_model(DimensionSetEntry)
