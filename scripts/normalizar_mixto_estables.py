"""Unifica los aliases históricos de Mixto Bs As con los servicios canónicos."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "instance" / "facturacion.db"
BACKUP_DIR = ROOT / ".cache"


def totales(connection: sqlite3.Connection) -> dict[str, float]:
    row = connection.execute(
        """
        SELECT COUNT(*) registros,
               COALESCE(SUM(horas_objetivo), 0) horas_objetivo,
               COALESCE(SUM(horas_facturadas), 0) horas_facturadas,
               COALESCE(SUM(COALESCE(control_objetivo_total,
                   horas_objetivo * COALESCE(valor_hora_objetivo, valor_hora)
                   + COALESCE(variable_objetivo, 0))), 0) objetivo,
               COALESCE(SUM(COALESCE(control_total_facturado, total_facturado_manual,
                   COALESCE(facturado_horas_manual, horas_facturadas * valor_hora)
                   + COALESCE(tarifacion, 0) + COALESCE(variable_productivo, 0)
                   + COALESCE(bonos, 0) - ABS(COALESCE(penalizaciones, 0))
                   + COALESCE(netx_gen, 0) + COALESCE(otros, 0))), 0) facturado
        FROM facturacion_anio
        WHERE LOWER(campania) IN (
            'santander mixto bs as', 'santander mixto estables',
            'mixto estables', 'santander mixto ingresos', 'mixto ingresos'
        )
        """
    ).fetchone()
    return {
        "registros": int(row[0]),
        "horas_objetivo": round(float(row[1]), 2),
        "horas_facturadas": round(float(row[2]), 2),
        "objetivo": round(float(row[3]), 2),
        "facturado": round(float(row[4]), 2),
    }


def main() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_DIR / f"facturacion-before-mixto-estables-{timestamp}.db"
    shutil.copy2(DATABASE, backup)

    connection = sqlite3.connect(DATABASE, timeout=30)
    antes = totales(connection)
    cambios: dict[str, int] = {}
    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute(
            """
            UPDATE facturacion_anio
               SET campania = 'Mixto Ingresos', subcampania = 'Mixto Ingresos'
             WHERE LOWER(campania) = 'santander mixto bs as'
               AND LOWER(COALESCE(subcampania, '')) LIKE '%ingresos%'
            """
        )
        cambios["facturacion_ingresos"] = cursor.rowcount

        cursor = connection.execute(
            """
            UPDATE facturacion_anio
               SET campania = 'Mixto Estables', subcampania = 'Mixto Estables'
             WHERE LOWER(campania) IN ('santander mixto bs as', 'santander mixto estables')
            """
        )
        cambios["facturacion_estables"] = cursor.rowcount

        for table in ("matriz_proyecciones", "matriz_precios"):
            cursor = connection.execute(
                f"UPDATE {table} SET campania = 'Mixto Estables' "
                "WHERE LOWER(campania) IN ('santander mixto bs as', 'santander mixto estables')"
            )
            cambios[f"{table}_estables"] = cursor.rowcount
            cursor = connection.execute(
                f"UPDATE {table} SET campania = 'Mixto Ingresos' "
                "WHERE LOWER(campania) IN ('santander mixto bs as ingresos', 'santander mixto ingresos')"
            )
            cambios[f"{table}_ingresos"] = cursor.rowcount

        cursor = connection.execute(
            """
            UPDATE asignaciones_comerciales
               SET campania = 'Mixto Ingresos', subcampania = 'Mixto Ingresos',
                   campania_id = (SELECT id FROM campanias
                                  WHERE cliente = 'Santander' AND nombre = 'Mixto Ingresos'),
                   activa = 0
             WHERE LOWER(campania) = 'santander mixto bs as'
               AND LOWER(subcampania) LIKE '%ingresos%'
            """
        )
        cambios["asignaciones_ingresos_desactivadas"] = cursor.rowcount
        cursor = connection.execute(
            """
            UPDATE asignaciones_comerciales
               SET campania = 'Mixto Estables', subcampania = 'Mixto Estables',
                   campania_id = (SELECT id FROM campanias
                                  WHERE cliente = 'Santander' AND nombre = 'Mixto Estables'),
                   activa = 0
             WHERE LOWER(campania) = 'santander mixto bs as'
            """
        )
        cambios["asignaciones_estables_desactivadas"] = cursor.rowcount
        cursor = connection.execute(
            "UPDATE campanias SET activa = 0 "
            "WHERE cliente = 'Santander' AND LOWER(nombre) = 'santander mixto bs as' AND activa != 0"
        )
        cambios["catalogos_desactivados"] = cursor.rowcount

        # El tablero operativo conserva el nombre crudo de origen. Solo se
        # corrige su clasificación normalizada para los cruces posteriores.
        operativos = connection.execute(
            "SELECT id, datos FROM dashboard_operativo "
            "WHERE LOWER(datos) LIKE '%santander mixto bs as%'"
        ).fetchall()
        actualizados_operativos = 0
        for registro_id, contenido in operativos:
            try:
                datos = json.loads(contenido)
            except (TypeError, json.JSONDecodeError):
                continue
            campania_origen = str(datos.get("campania") or "").lower()
            datos["cliente_normalizado"] = (
                "Mixto Ingresos" if "ingresos" in campania_origen else "Mixto Estables"
            )
            connection.execute(
                "UPDATE dashboard_operativo SET datos = ? WHERE id = ?",
                (json.dumps(datos, ensure_ascii=False), registro_id),
            )
            actualizados_operativos += 1
        cambios["dashboard_operativo"] = actualizados_operativos

        despues = totales(connection)
        if antes != despues:
            raise RuntimeError(f"Los totales cambiaron: antes={antes}, despues={despues}")

        if any(cambios.values()):
            connection.execute(
                """
                INSERT INTO historial_cambios
                    (usuario_nombre, accion, entidad, entidad_id, resumen, detalle,
                     antes, despues, creado_en)
                VALUES
                    ('Sistema', 'edicion', 'normalizacion_campanias', 'mixto-estables',
                     'Mixto Bs As unificado con Mixto Estables', ?, ?, ?, ?)
                """,
                (
                    json.dumps(cambios, ensure_ascii=False),
                    json.dumps({"nombres": ["Santander Mixto Bs As", "Santander Mixto Estables"]}, ensure_ascii=False),
                    json.dumps({"estables": "Mixto Estables", "ingresos": "Mixto Ingresos"}, ensure_ascii=False),
                    datetime.now().isoformat(sep=" ", timespec="microseconds"),
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(json.dumps({"backup": str(backup), "cambios": cambios, "totales": despues}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
