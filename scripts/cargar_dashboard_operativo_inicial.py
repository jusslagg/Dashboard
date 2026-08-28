import json
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import DashboardOperativo
from app.routes import DASHBOARD_COLUMNAS


archivo = r"C:\Users\jegil\Downloads\2026 Facturacion (32).xlsx"
libro = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
hoja = libro["Dashboard"]
app = create_app()
with app.app_context():
    db.create_all()
    cantidad = 0
    for row in hoja.iter_rows(min_row=3, values_only=True):
        valores = list(row)
        if len(valores) < 41:
            valores += [None] * (41 - len(valores))
        fecha, cliente, campania = valores[5], str(valores[6] or "").strip(), str(valores[7] or "").strip()
        if not isinstance(fecha, (datetime, date)) or not cliente or not campania:
            continue
        clave_mes = fecha.strftime("%Y-%m")
        registro = DashboardOperativo.query.filter_by(mes=clave_mes, cliente=cliente, campania=campania).first()
        if not registro:
            registro = DashboardOperativo(
                year=fecha.year, mes=clave_mes, cliente=cliente, campania=campania,
                bajas_manual=float(valores[40] or 0),
            )
            db.session.add(registro)
        datos = {}
        for indice, clave in enumerate(DASHBOARD_COLUMNAS):
            valor = valores[indice + 1]
            datos[clave] = valor.isoformat() if isinstance(valor, (datetime, date)) else valor
        datos.update({"mes": clave_mes, "cliente": cliente, "campania": campania})
        datos.pop("agentes_baja", None)
        registro.datos = json.dumps(datos, ensure_ascii=False)
        cantidad += 1
    db.session.commit()
    print(f"Dashboard operativo cargado: {cantidad} filas")
