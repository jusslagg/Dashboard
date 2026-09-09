import json
import sqlite3
import sys
from pathlib import Path

from flask import session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import Facturacion2026
from app.routes import cambios_entre, registrar_historial, snapshot_modelo


DB_PATH = Path("instance/facturacion.db")
BACKUP_PATH = Path("instance/facturacion_20260907_before_hour_reconciliation.db")
ORIGINAL_IDS = (1453, 1454, 1455)
DUPLICATE_IDS = (1456, 1457, 1458)


def backup_database():
    if BACKUP_PATH.exists():
        raise RuntimeError(f"El respaldo ya existe: {BACKUP_PATH}")
    with sqlite3.connect(DB_PATH) as source, sqlite3.connect(BACKUP_PATH) as target:
        source.backup(target)


def comparable(record):
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
        if column.name != "id"
    }


def reconcile():
    app = create_app()
    with app.test_request_context("/reconciliacion-horas"):
        session["usuario_id"] = 1

        originals = [db.session.get(Facturacion2026, row_id) for row_id in ORIGINAL_IDS]
        duplicates = [db.session.get(Facturacion2026, row_id) for row_id in DUPLICATE_IDS]
        if any(record is None for record in originals + duplicates):
            raise RuntimeError("No se encontraron todas las filas del lote duplicado")
        for original, duplicate in zip(originals, duplicates):
            if comparable(original) != comparable(duplicate):
                raise RuntimeError(f"Las filas {original.id} y {duplicate.id} ya no son idénticas")

        gire = db.session.get(Facturacion2026, 1413)
        if not gire or gire.cliente != "Gire" or gire.mes != "2026-08":
            raise RuntimeError("No se encontró el registro esperado de Gire")
        if float(gire.horas_objetivo) != 1419 or float(gire.horas_facturadas) != 1347.73:
            raise RuntimeError("El registro de Gire cambió desde la conciliación")

        for duplicate in duplicates:
            before = snapshot_modelo(duplicate)
            registrar_historial(
                "eliminacion",
                "facturacion",
                duplicate.id,
                f"Conciliación Excel: lote duplicado de {duplicate.cliente} / {duplicate.mes}",
                antes=before,
                detalle=(
                    f"Se retiró la copia duplicada del registro {duplicate.id}; "
                    f"se conserva el registro {duplicate.id - 3}."
                ),
            )
            db.session.delete(duplicate)

        before_gire = snapshot_modelo(gire)
        gire.horas_objetivo = 1470
        after_gire = snapshot_modelo(gire)
        registrar_historial(
            "edicion",
            "facturacion",
            gire.id,
            "Conciliación Excel: Gire / 2026-08",
            antes=before_gire,
            despues=after_gire,
            detalle=json.dumps(cambios_entre(before_gire, after_gire), ensure_ascii=False),
        )

        db.session.commit()


if __name__ == "__main__":
    backup_database()
    try:
        reconcile()
    except Exception:
        db.session.rollback()
        raise
    print(f"Respaldo: {BACKUP_PATH}")
    print("Conciliación aplicada")
