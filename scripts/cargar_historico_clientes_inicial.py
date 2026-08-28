"""Carga inicial del Histórico del Excel, agrupado por mes y cliente."""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openpyxl import load_workbook
from app import create_app, db
from app.models import DashboardOperativo, FacturacionAnio, HistoricoClienteMensual

ARCHIVO = r'C:\Users\jegil\Downloads\2026 Facturacion (32).xlsx'

def num(v):
    try: return float(v or 0)
    except (TypeError, ValueError): return 0.0

app = create_app()
with app.app_context():
    db.create_all()
    hoja = load_workbook(ARCHIVO, data_only=True, read_only=True)['Historico']
    grupos = defaultdict(lambda: {'empresa': '', 'site': '', 'industria': '',
        'horas_dotacion_activa': 0, 'horas_ausentismo': 0, 'dotacion_promedio': 0,
        'bajas': 0, 'horas_requeridas': 0, 'horas_realizadas': 0,
        'pagadas': 0, 'logueo': 0, 'dotacion_requerida': 0})
    manual_presente = defaultdict(lambda: [False, False])
    for row in hoja.iter_rows(min_row=3, max_col=21, values_only=True):
        fecha, cliente = row[5], str(row[3] or '').strip()
        if not fecha or not cliente: continue
        mes = fecha.strftime('%Y-%m')
        d = grupos[(mes, cliente)]
        d['empresa'], d['site'], d['industria'] = row[0] or d['empresa'], row[1] or d['site'], row[2] or d['industria']
        for key, idx in [('horas_dotacion_activa',8),('horas_ausentismo',9),('dotacion_promedio',10),
                         ('bajas',11),('horas_requeridas',12),('horas_realizadas',13),
                         ('pagadas',14),('logueo',15),('dotacion_requerida',20)]:
            d[key] += num(row[idx])
        manual_presente[(mes, cliente)][0] |= row[14] not in (None, '')
        manual_presente[(mes, cliente)][1] |= row[15] not in (None, '')
    for (mes, cliente), d in grupos.items():
        registro = HistoricoClienteMensual.query.filter_by(mes=mes, cliente=cliente).first()
        if not registro:
            registro = HistoricoClienteMensual(year=int(mes[:4]), mes=mes, cliente=cliente)
            db.session.add(registro)
        registro.datos_base = json.dumps({k:v for k,v in d.items() if k not in ('pagadas','logueo')}, ensure_ascii=False)
        registro.pagadas = d['pagadas'] if manual_presente[(mes,cliente)][0] else None
        registro.logueo = d['logueo'] if manual_presente[(mes,cliente)][1] else None
    facturas = defaultdict(lambda: [0, 0])
    for fila in FacturacionAnio.query.all():
        clave = (fila.fecha.strftime('%Y-%m'), fila.cliente)
        facturas[clave][0] += num(fila.horas_objetivo)
        facturas[clave][1] += num(fila.horas_facturadas)
    for (mes, cliente), (objetivo, realizadas) in facturas.items():
        registro = HistoricoClienteMensual.query.filter_by(mes=mes, cliente=cliente).first()
        if not registro:
            registro = HistoricoClienteMensual(year=int(mes[:4]), mes=mes, cliente=cliente,
                                               pagadas=None, logueo=None)
            db.session.add(registro)
            base = {'_ocultar_sin_cambios': True}
        else:
            base = registro.base_dict()
        base['_fact_snapshot_obj'] = objetivo
        base['_fact_snapshot_real'] = realizadas
        registro.datos_base = json.dumps(base, ensure_ascii=False)
    for fila in DashboardOperativo.query.all():
        if HistoricoClienteMensual.query.filter_by(mes=fila.mes, cliente=fila.cliente).first():
            continue
        db.session.add(HistoricoClienteMensual(
            year=fila.year, mes=fila.mes, cliente=fila.cliente,
            datos_base=json.dumps({'_ocultar_sin_cambios': True}, ensure_ascii=False),
        ))
    db.session.commit()
    print(f'Cargados {len(grupos)} registros históricos por cliente y mes.')
