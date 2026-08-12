"""Genera el DDL completo de la aplicación para SQLite y PostgreSQL.

Los archivos resultantes son el contrato físico que puede recibir un tercero
para crear o revisar la base sin depender de una base local preexistente.
"""

from __future__ import annotations

import html
from pathlib import Path
import sys


RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from app import db
import app.models  # noqa: F401 - registra todos los modelos en db.metadata


DESTINOS = {
    "sqlite": (sqlite.dialect(), RAIZ / "docs" / "esquema_base_datos_sqlite.sql"),
    "postgresql": (postgresql.dialect(), RAIZ / "docs" / "esquema_base_datos_postgresql.sql"),
}


def compilar(elemento, dialecto) -> str:
    texto = str(elemento.compile(dialect=dialecto)).strip()
    return "\n".join(linea.rstrip() for linea in texto.splitlines())


def generar(nombre: str, dialecto, destino: Path) -> None:
    lineas = [
        "-- Dashboard de Facturación",
        f"-- Esquema físico completo para {nombre.upper()}",
        "-- Generado desde app/models.py. No editar manualmente.",
        "",
    ]

    for tabla in db.metadata.sorted_tables:
        lineas.extend([
            f"-- ============================================================",
            f"-- TABLA: {tabla.name}",
            f"-- ============================================================",
            compilar(CreateTable(tabla), dialecto) + ";",
            "",
        ])
        for indice in sorted(tabla.indexes, key=lambda item: item.name or ""):
            lineas.extend([compilar(CreateIndex(indice), dialecto) + ";", ""])

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(lineas).rstrip() + "\n", encoding="utf-8")
    print(f"Generado: {destino}")


def generar_html_pdf() -> None:
    """Genera la fuente HTML del PDF específico de esquemas."""
    sqlite_ddl = (RAIZ / "docs" / "esquema_base_datos_sqlite.sql").read_text(encoding="utf-8")
    postgres_ddl = (RAIZ / "docs" / "esquema_base_datos_postgresql.sql").read_text(encoding="utf-8")
    documento = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Esquema de base de datos</title>
<style>
body{{font:12px/1.45 Arial,sans-serif;color:#172033;margin:35px}}
h1{{color:#0f2747;font-size:28px}} h2{{color:#174b83;border-bottom:2px solid #0891b2;padding-bottom:8px;break-before:page}}
.portada{{break-after:page}} pre{{white-space:pre-wrap;font:9px/1.35 Consolas,monospace;background:#f4f7fb;border:1px solid #dbe4ef;padding:14px}}
@page{{size:A4;margin:15mm}}
</style></head><body>
<section class="portada"><h1>Dashboard de Facturación</h1><h3>Esquema físico completo de base de datos</h3>
<p>Documento técnico para creación y revisión por el responsable de base de datos.</p>
<p>Incluye las 16 tablas, columnas, tipos, claves primarias, claves foráneas, restricciones únicas e índices para SQLite y PostgreSQL.</p></section>
<h2>DDL completo — SQLite</h2><pre>{html.escape(sqlite_ddl)}</pre>
<h2>DDL completo — PostgreSQL</h2><pre>{html.escape(postgres_ddl)}</pre>
</body></html>"""
    destino = RAIZ / "docs" / "esquema_base_datos.html"
    destino.write_text(documento, encoding="utf-8")
    print(f"Generado: {destino}")


def main() -> None:
    for nombre, (dialecto, destino) in DESTINOS.items():
        generar(nombre, dialecto, destino)
    generar_html_pdf()


if __name__ == "__main__":
    main()
