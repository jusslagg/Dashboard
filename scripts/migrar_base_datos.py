"""Copia una base completa a un destino vacío y verifica paridad.

Uso recomendado para PostgreSQL:

    python scripts/migrar_base_datos.py \
      --source-url sqlite:///C:/ruta/instance/facturacion.db \
      --target-url postgresql+psycopg://usuario:clave@host/base

El origen se abre únicamente para lectura. El destino debe estar vacío para
evitar mezclas o duplicados; el script no borra datos existentes.
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import func, inspect, select, text

from database_contract import (
    database_manifest,
    default_database_url,
    engine_for,
    manifest_differences,
    model_metadata,
    safe_url,
)


def ensure_empty(connection, metadata) -> None:
    existing = set(inspect(connection).get_table_names())
    occupied = []
    for table in metadata.sorted_tables:
        if table.name not in existing:
            continue
        count = connection.execute(select(func.count()).select_from(table)).scalar_one()
        if count:
            occupied.append(f"{table.name} ({count})")
    if occupied:
        raise RuntimeError(
            "La base destino contiene datos. Cree una base vacía antes de migrar: "
            + ", ".join(occupied)
        )


def reset_postgresql_sequences(connection, metadata) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table in metadata.sorted_tables:
        for column in table.primary_key.columns:
            sequence = connection.execute(
                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                {"table_name": table.name, "column_name": column.name},
            ).scalar_one_or_none()
            if not sequence:
                continue
            maximum = connection.execute(select(func.max(column))).scalar_one()
            if maximum is None:
                connection.execute(
                    text("SELECT setval(CAST(:sequence AS regclass), 1, false)"),
                    {"sequence": sequence},
                )
            else:
                connection.execute(
                    text("SELECT setval(CAST(:sequence AS regclass), :value, true)"),
                    {"sequence": sequence, "value": int(maximum)},
                )


def copy_database(source_engine, target_engine, chunk_size: int = 500) -> None:
    metadata = model_metadata()
    source_tables = set(inspect(source_engine).get_table_names())
    missing = [table.name for table in metadata.sorted_tables if table.name not in source_tables]
    if missing:
        raise RuntimeError(f"La base origen no cumple el contrato; faltan: {', '.join(missing)}")

    metadata.create_all(target_engine)
    with source_engine.connect() as source, target_engine.begin() as target:
        if target.dialect.name == "sqlite":
            target.execute(text("PRAGMA foreign_keys=ON"))
        ensure_empty(target, metadata)
        for table in metadata.sorted_tables:
            rows = []
            copied = 0
            for row in source.execute(select(table)).mappings():
                rows.append(dict(row))
                if len(rows) >= chunk_size:
                    target.execute(table.insert(), rows)
                    copied += len(rows)
                    rows.clear()
            if rows:
                target.execute(table.insert(), rows)
                copied += len(rows)
            print(f"{table.name}: {copied} fila(s)")
        reset_postgresql_sequences(target, metadata)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra todas las tablas a una base vacía y comprueba igualdad de contenido."
    )
    parser.add_argument("--source-url", default=default_database_url())
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL"))
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()
    if not args.target_url:
        parser.error("Indique --target-url o TARGET_DATABASE_URL.")
    if args.source_url == args.target_url:
        parser.error("Origen y destino no pueden ser la misma base.")
    if args.chunk_size < 1:
        parser.error("--chunk-size debe ser mayor que cero.")

    print(f"Origen: {safe_url(args.source_url)}")
    print(f"Destino: {safe_url(args.target_url)}")
    source_engine = engine_for(args.source_url)
    target_engine = engine_for(args.target_url)
    try:
        copy_database(source_engine, target_engine, args.chunk_size)
        source_manifest = database_manifest(source_engine)
        target_manifest = database_manifest(target_engine)
        differences = manifest_differences(source_manifest, target_manifest)
        if differences:
            print("La copia terminó, pero la validación de paridad falló:")
            for difference in differences:
                print(f"- {difference}")
            return 1
        print("MIGRACIÓN OK: esquema, cantidad de filas y contenido coinciden.")
        return 0
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
