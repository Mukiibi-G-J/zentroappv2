# Generated manually - Migrate Dimension and DimensionValue from code (CharField) PK to id (AutoField) PK

from django.db import migrations, models


def migrate_dimension_pk_to_id(apps, schema_editor):
    """
    Migrate dimension_dimension and dimension_dimensionvalue from code (varchar) PK
    to id (integer) PK. Updates all FK columns across the database.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        # Flush any deferred constraints to avoid "pending trigger events"
        try:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        except Exception:
            pass
        # ==================== PHASE 1: DIMENSION TABLE ====================
        # 1.1 Add id column to dimension_dimension (BIGSERIAL auto-populates existing rows)
        cursor.execute("""
            ALTER TABLE dimension_dimension
            ADD COLUMN IF NOT EXISTS id BIGSERIAL
        """)
        # Backfill any NULLs (e.g. from partial previous run)
        cursor.execute("""
            UPDATE dimension_dimension d SET id = sub.n
            FROM (
                SELECT code, (SELECT COALESCE(MAX(id),0) FROM dimension_dimension) +
                    row_number() OVER (ORDER BY code) AS n
                FROM dimension_dimension WHERE id IS NULL
            ) sub WHERE d.code = sub.code AND d.id IS NULL
        """)
        # Add UNIQUE on id so FKs can reference it (before we drop code PK)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimension ADD CONSTRAINT dimension_dimension_id_key UNIQUE (id);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)

        # 1.3 Migrate FK columns for Dimension references (now id is PK)
        # Discover all FKs dynamically (handles hotel_management, items_location, etc.)
        dim_fk_refs = _get_fk_refs(cursor, "dimension_dimension")
        for table, column, ref_table in dim_fk_refs:
            _migrate_fk_column(cursor, table, column, ref_table, "code", "id")

        # 1.4 Drop old PK, promote id to PK, add unique on code
        # (Keep id_key - FKs depend on it; PK will provide uniqueness)
        cursor.execute("""
            ALTER TABLE dimension_dimension DROP CONSTRAINT IF EXISTS dimension_dimension_pkey
        """)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimension ADD CONSTRAINT dimension_dimension_pkey PRIMARY KEY (id);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimension ADD CONSTRAINT dimension_dimension_code_key UNIQUE (code);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)

        # ==================== PHASE 2: DIMENSIONVALUE TABLE ====================
        # 2.1 Add id column to dimension_dimensionvalue
        cursor.execute("""
            ALTER TABLE dimension_dimensionvalue
            ADD COLUMN IF NOT EXISTS id BIGSERIAL
        """)
        cursor.execute("""
            UPDATE dimension_dimensionvalue dv SET id = sub.n
            FROM (
                SELECT code, (SELECT COALESCE(MAX(id),0) FROM dimension_dimensionvalue) +
                    row_number() OVER (ORDER BY code) AS n
                FROM dimension_dimensionvalue WHERE id IS NULL
            ) sub WHERE dv.code = sub.code AND dv.id IS NULL
        """)
        # Add UNIQUE on id so FKs can reference it
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimensionvalue ADD CONSTRAINT dimension_dimensionvalue_id_key UNIQUE (id);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)

        # 2.2 Migrate FK columns for DimensionValue references
        # Discover all FKs dynamically (handles hotel_management, items_location, etc.)
        dimval_fk_refs = _get_fk_refs(cursor, "dimension_dimensionvalue")
        for table, column, ref_table in dimval_fk_refs:
            _migrate_fk_column(cursor, table, column, ref_table, "code", "id")

        # 2.3 Drop old PK, promote id to PK, add unique on code
        cursor.execute("""
            ALTER TABLE dimension_dimensionvalue DROP CONSTRAINT IF EXISTS dimension_dimensionvalue_pkey
        """)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimensionvalue ADD CONSTRAINT dimension_dimensionvalue_pkey PRIMARY KEY (id);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE dimension_dimensionvalue ADD CONSTRAINT dimension_dimensionvalue_code_key UNIQUE (code);
            EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
            END $$;
        """)


def _get_fk_refs(cursor, ref_table):
    """Discover all (table, column) pairs that have FK to ref_table in current schema."""
    cursor.execute("""
        SELECT tc.relname AS table_name,
               a.attname AS column_name
        FROM pg_constraint c
        JOIN pg_class tc ON c.conrelid = tc.oid
        JOIN pg_namespace tn ON tc.relnamespace = tn.oid
        JOIN pg_class rc ON c.confrelid = rc.oid
        JOIN pg_namespace rn ON rc.relnamespace = rn.oid
        JOIN pg_attribute a ON a.attrelid = tc.oid AND a.attnum = ANY(c.conkey) AND a.attisdropped = false
        WHERE tn.nspname = current_schema()
        AND rn.nspname = current_schema()
        AND rc.relname = %s
        AND c.contype = 'f'
    """, [ref_table])
    result = []
    for (tname, cname) in cursor.fetchall():
        # Quote table name if it has spaces (e.g. "Item Ledger Entries")
        table_ref = f'"{tname}"' if " " in tname else tname
        result.append((table_ref, cname, ref_table))
    return result


def _migrate_fk_column(cursor, table, column, ref_table, old_ref_col, new_ref_col):
    """
    Migrate an FK column from storing old_ref_col (varchar) to new_ref_col (integer).
    - Add temp integer column
    - Populate from ref_table mapping
    - Drop FK constraint
    - Drop old column
    - Rename temp to column
    - Add new FK constraint
    """
    table_clean = table.strip('"')
    temp_col = f"{column}_new"

    # Check if table and column exist; skip if column is already integer (idempotent re-run)
    cursor.execute("""
        SELECT c.data_type FROM information_schema.columns c
        WHERE c.table_schema = current_schema()
        AND c.table_name = %s
        AND c.column_name = %s
    """, [table_clean, column])
    row = cursor.fetchone()
    if not row:
        return
    if row[0] in ("bigint", "integer", "smallint"):
        return  # Already migrated to integer

    # Add temp column
    cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{temp_col}" BIGINT')
    # Populate from mapping (old column has varchar code, map to ref_table.id)
    cursor.execute(f"""
        UPDATE {table} t
        SET "{temp_col}" = r.{new_ref_col}
        FROM {ref_table} r
        WHERE t."{column}"::text = r.{old_ref_col}::text
    """)
    # Drop FK constraints pointing from this table to ref_table
    cursor.execute("""
        SELECT c.conname FROM pg_constraint c
        JOIN pg_class tc ON c.conrelid = tc.oid
        JOIN pg_namespace tn ON tc.relnamespace = tn.oid
        JOIN pg_class rc ON c.confrelid = rc.oid
        JOIN pg_namespace rn ON rc.relnamespace = rn.oid
        WHERE tn.nspname = current_schema()
        AND tc.relname = %s
        AND rn.nspname = current_schema()
        AND rc.relname = %s
        AND c.contype = 'f'
    """, [table_clean, ref_table])
    for (conname,) in cursor.fetchall():
        try:
            cursor.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{conname}"')
        except Exception as e:
            if "pending trigger events" in str(e).lower():
                try:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    cursor.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{conname}"')
                except Exception:
                    raise e
            else:
                raise
    # Drop old column
    cursor.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"')
    # Rename temp to original
    cursor.execute(f'ALTER TABLE {table} RENAME COLUMN "{temp_col}" TO "{column}"')
    # Add FK constraint (constraint name must be unique, no spaces)
    constraint_name = f"{table_clean.replace(' ', '_')}_{column}_fkey"[:63]
    cursor.execute(f"""
        ALTER TABLE {table}
        ADD CONSTRAINT "{constraint_name}"
        FOREIGN KEY ("{column}") REFERENCES {ref_table}({new_ref_col})
    """)


def reverse_migrate(apps, schema_editor):
    """
    Reverse migration: change back to code PK.
    Note: This is destructive if new integer ids were created - original code values must be preserved.
    For safety, we leave this as a no-op; run forward migration only.
    """
    raise RuntimeError(
        "Reverse migration not supported: Dimension/DimensionValue PK change is one-way. "
        "Restore from backup if rollback is required."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("dimension", "0002_defaultdimension"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # Dimension: change PK from code to id
                migrations.AlterField(
                    model_name="dimension",
                    name="code",
                    field=models.CharField(max_length=255, unique=True),
                ),
                migrations.AddField(
                    model_name="dimension",
                    name="id",
                    field=models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                # DimensionValue: change PK from code to id
                migrations.AlterField(
                    model_name="dimensionvalue",
                    name="code",
                    field=models.CharField(max_length=255, unique=True),
                ),
                migrations.AddField(
                    model_name="dimensionvalue",
                    name="id",
                    field=models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(migrate_dimension_pk_to_id, reverse_migrate),
            ],
        ),
    ]
