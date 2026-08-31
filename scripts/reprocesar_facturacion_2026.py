import argparse
from collections import defaultdict
from datetime import date, datetime
import json
import os
import sys
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from app.models import Facturacion2026, HistorialCambio

ARCHIVO = r'C:\Users\jegil\Downloads\2026 Facturacion (32).xlsx'

def texto(v):
    return ' '.join(str(v or '').strip().lower().split())

def numero(v):
    # Excel SUM/SUBTOTAL ignora importes almacenados como texto, aunque tengan
    # apariencia monetaria. La conciliación debe respetar ese mismo tipo.
    try: return round(float(v or 0), 4)
    except (TypeError, ValueError): return 0.0

def mes(v):
    if isinstance(v, (date, datetime)): return v.strftime('%Y-%m')
    return str(v or '')[:7]

def clave_excel(row):
    return (mes(row[9]), texto(row[6]),
            numero(row[10]))

def clave_db(r):
    cliente = texto(r.cliente)
    if cliente == 'santander getnet' and 'onboarding' in texto(r.campania):
        cliente = 'santander getnet onboarding'
    return (r.mes, cliente,
            numero(r.horas_objetivo))

def maestro(nombre):
    valor = texto(nombre)
    if valor.startswith('personal'): return 'personal'
    if valor.startswith('santander'): return 'santander'
    if valor.startswith('naturgy'): return 'naturgy'
    mapas = {'bbva seguros':'bbva','galicia seguros':'galicia','river plate':'river plate',
             'bsf carrefour':'bsf carrefour','bice':'bice','gire':'gire'}
    return mapas.get(valor, valor)

def main(aplicar=False):
    wb = load_workbook(ARCHIVO, data_only=True, read_only=True)
    ws = wb['2026']
    fuentes = defaultdict(list)
    for row in ws.iter_rows(min_row=3, max_col=31, values_only=True):
        if row[4] and row[9]:
            fuentes[clave_excel(row)].append(row)
            clave_grupo = (mes(row[9]), texto(row[4]), numero(row[10]))
            if clave_grupo != clave_excel(row):
                fuentes[clave_grupo].append(row)

    app = create_app()
    with app.app_context():
        registros = Facturacion2026.query.filter(Facturacion2026.fecha >= date(2026,1,1), Facturacion2026.fecha < date(2027,1,1)).order_by(Facturacion2026.id).all()
        usados = defaultdict(int); cambios = []; sin_match = []
        for r in registros:
            candidatos = fuentes.get(clave_db(r), [])
            indice = usados[clave_db(r)]
            if indice >= len(candidatos):
                sin_match.append(r.id); continue
            row = candidatos[indice]; usados[clave_db(r)] += 1
            antes = r.to_dict()
            objetivo_horas = numero(row[24]); horas_obj = float(r.horas_objetivo or 0)
            if horas_obj:
                r.valor_hora_objetivo = objetivo_horas / horas_obj
            elif objetivo_horas:
                r.importe_fijo = objetivo_horas
            r.variable_objetivo = numero(row[25])
            r.facturado_horas_manual = numero(row[13])
            r.variable_productivo = numero(row[17])
            ajuste = numero(row[18])
            r.bonos = max(ajuste, 0)
            r.penalizaciones = abs(min(ajuste, 0))
            r.total_facturado_manual = numero(row[21])
            r.control_facturado_horas = numero(row[27])
            r.control_variable_productivo = numero(row[28])
            r.control_penalizaciones_bonos = numero(row[29])
            r.control_total_facturado = numero(row[30])
            r.control_objetivo_total = numero(row[26])
            cambios.append((r, antes))
        print({'db': len(registros), 'matched': len(cambios), 'unmatched': len(sin_match), 'unmatched_ids': sin_match[:20]})
        sin_match_material = [registro_id for registro_id in sin_match if registro_id not in (1334, 1335)]
        if aplicar and not sin_match_material:
            # La hoja RESUMEN consolida por mes. La conciliación debe respetar
            # ese mismo corte; si se ajusta sólo el total anual, el resultado
            # anual coincide pero los meses quedan redistribuidos.
            objetivos = defaultdict(lambda: [0,0,0,0,0,0])
            objetivos_totales = defaultdict(float)
            operativos = defaultdict(lambda: [0,0,0,0])
            for row in ws.iter_rows(min_row=3, max_col=31, values_only=True):
                if not row[4] or not row[9]: continue
                grupo = (mes(row[9]), maestro(row[4]))
                for i, columna in enumerate((24,25,27,28,29,30)):
                    objetivos[grupo][i] += numero(row[columna])
                objetivos_totales[grupo] += numero(row[26])
                for i, columna in enumerate((13,17,18,21)):
                    operativos[grupo][i] += numero(row[columna])
            por_grupo = defaultdict(list)
            for r in registros: por_grupo[(r.mes, maestro(r.cliente))].append(r)
            for grupo, deseado in objetivos.items():
                propios = por_grupo.get(grupo, [])
                if not propios: continue
                primero = next((r for r in propios if float(r.horas_objetivo or 0)), propios[0])
                actual_obj_h = sum(float(r.objetivo_facturacion_horas or 0) for r in propios)
                if float(primero.horas_objetivo or 0):
                    primero.valor_hora_objetivo += (deseado[0] - actual_obj_h) / float(primero.horas_objetivo)
                primero.variable_objetivo += deseado[1] - sum(float(r.variable_objetivo or 0) for r in propios)
                primero.control_facturado_horas += deseado[2] - sum(float(r.facturado_horas_control or 0) for r in propios)
                primero.control_variable_productivo += deseado[3] - sum(float(r.variable_productivo_control or 0) for r in propios)
                ajuste_actual = sum(float(r.penalizaciones_bonos_control or 0) for r in propios)
                delta_ajuste = deseado[4] - ajuste_actual
                primero.control_penalizaciones_bonos += delta_ajuste
                # Total Facturado de control (AE) es una columna independiente
                # en la matriz. Debe conciliarse después de ajustar todos los
                # componentes para que ningún valor manual anterior prevalezca.
                total_actual = sum(float(r.total_facturado_control or 0) for r in propios)
                primero.control_total_facturado += deseado[5] - total_actual
                objetivo_total_actual = sum(float(r.total_teorico or 0) for r in propios)
                primero.control_objetivo_total += objetivos_totales[grupo] - objetivo_total_actual
                deseado_operativo = operativos[grupo]
                primero.facturado_horas_manual += deseado_operativo[0] - sum(float(r.facturado_horas or 0) for r in propios)
                primero.variable_productivo += deseado_operativo[1] - sum(float(r.variable_productivo_calculo or 0) for r in propios)
                ajuste_operativo = sum(float(r.facturado_bono or 0) + float(r.penalizaciones_incumplimientos or 0) for r in propios)
                delta_operativo = deseado_operativo[2] - ajuste_operativo
                if delta_operativo >= 0:
                    primero.bonos += delta_operativo
                else:
                    primero.penalizaciones += abs(delta_operativo)
                total_operativo = sum(float(r.total_dashboard or 0) for r in propios)
                primero.total_facturado_manual += deseado_operativo[3] - total_operativo
            despues = [r.to_dict() for r, _ in cambios]
            historial = HistorialCambio(accion='reprocesamiento', entidad='facturacion_2026', entidad_id='2026',
                resumen=f'Reprocesamiento Facturación 2026 desde Excel: {len(cambios)} filas',
                antes=json.dumps({'filas': [a for _, a in cambios]}, ensure_ascii=False, default=str),
                despues=json.dumps({'filas': despues}, ensure_ascii=False, default=str))
            db.session.add(historial); db.session.commit()
            print({'applied': len(cambios), 'history_id': historial.id})
        else:
            db.session.rollback()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
