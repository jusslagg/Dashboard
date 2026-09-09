import json
import sqlite3

db = sqlite3.connect("instance/facturacion.db")
db.row_factory = sqlite3.Row

for row_id in (1413, 1453, 1454, 1455, 1456, 1457, 1458, 1459):
    row = db.execute("select * from facturacion_anio where id = ?", (row_id,)).fetchone()
    print("ROW", row_id, json.dumps(dict(row) if row else None, ensure_ascii=False, default=str))

print("HISTORY 1413")
for row in db.execute(
    "select * from historial_cambios where entidad = 'facturacion' and entidad_id = '1413' order by id"
):
    print(json.dumps(dict(row), ensure_ascii=False, default=str))

print("FOREIGN KEYS")
for table in ("justificacion_ajuste", "justificaciones_ajustes", "historial_cambios"):
    try:
        print(table, [dict(row) for row in db.execute(f"pragma foreign_key_list({table})")])
    except sqlite3.OperationalError as exc:
        print(table, str(exc))

print("RELATED TABLES")
for row in db.execute("select name from sqlite_master where type = 'table' order by name"):
    if "just" in row[0].lower():
        print(row[0], [dict(col) for col in db.execute(f"pragma table_info({row[0]})")])
