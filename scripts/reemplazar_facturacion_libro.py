"""Reemplaza un año de Facturación por la hoja homónima del libro operativo."""
import argparse
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Facturacion2026, HistorialCambio, normalizar_gerente, normalizar_jefe_site
from app.routes import jefe_personal_por_servicio, normalizar_header, normalizar_tipo_vh, segmento_personal_por_servicio


def numero(valor):
    if valor is None or (isinstance(valor, str) and valor.strip() in ('', '-')):
        return 0.0
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f'Valor no numérico: {valor!r}')
    return float(valor)


def texto(valor):
    return str(valor or '').strip()


def fila_facturacion(fila, year):
    fecha = fila[9]
    if not isinstance(fecha, (date, datetime)) or fecha.year != year or not texto(fila[4]):
        return None
    cliente, grupo, servicio = texto(fila[4]), texto(fila[6]), texto(fila[7])
    if not grupo or not servicio:
        raise ValueError('Falta cuenta o subcampaña')
    personal = normalizar_header(cliente) == 'personal'
    tipo = None
    gerente = texto(fila[5])
    jefe = texto(fila[1])
    if personal:
        grupo_clave = normalizar_header(grupo)
        tipo = ('Personal SMB' if 'smb' in grupo_clave else 'Personal Soporte' if 'soporte' in grupo_clave
                else 'Personal PPAY' if 'personal pay' in normalizar_header(servicio) else 'Personal CX')
        segmento = segmento_personal_por_servicio(grupo, servicio)
        jefe = normalizar_jefe_site(jefe_personal_por_servicio(tipo, segmento, servicio))
        if gerente == '#N/A' and normalizar_header(servicio) == 'ws convergente':
            gerente = 'Lucas Caamaño'
        campania = servicio
    else:
        campania = grupo
    gerente = normalizar_gerente(gerente) if gerente not in ('', '0', '#N/A') else None
    jefe = normalizar_jefe_site(jefe) if jefe not in ('', '0', '#N/A') else None
    # Validar todas las columnas numéricas utilizadas antes de escribir.
    for indice in (10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30):
        numero(fila[indice])
    objetivo = numero(fila[10])
    precio = numero(fila[12])
    precio_objetivo = numero(fila[22]) or precio
    objetivo_horas = numero(fila[24])
    ajuste = numero(fila[18])
    # Las filas sin horas cuyo único importe es Next Gen son de ese concepto.
    next_gen = bool(numero(fila[19]) and not any(numero(fila[i]) for i in (10, 11, 13, 14, 17, 18, 20)))
    meses = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
    mes_texto = normalizar_header(fila[0])
    mes_apertura = f'{year}-{meses.index(mes_texto) + 1:02d}' if mes_texto in meses else None
    return Facturacion2026(
        fecha=fecha.date() if isinstance(fecha, datetime) else fecha, mes=fecha.strftime('%Y-%m'),
        mes_apertura_origen=mes_apertura,
        cliente=cliente, gerente=gerente, jefe_site=jefe, campania=campania, subcampania=servicio,
        tipo_negocio=tipo, tipo_jornada=normalizar_tipo_vh(fila[8]) or 'Sin especificar', es_next_gen=next_gen,
        horas_objetivo=objetivo, horas_facturadas=numero(fila[11]), valor_hora=precio,
        valor_hora_objetivo=precio_objetivo,
        objetivo_separar_ajuste_vh=bool(objetivo and abs(objetivo_horas-objetivo*precio_objetivo) > .02
                                        and abs(objetivo_horas-objetivo*precio) <= .02),
        facturado_horas_manual=numero(fila[13]), tarifacion=numero(fila[14]),
        variable_productivo=numero(fila[17]), bonos=max(ajuste, 0), penalizaciones=abs(min(ajuste, 0)),
        netx_gen=numero(fila[19]), otros=numero(fila[20]), total_facturado_manual=numero(fila[21]),
        variable_objetivo=numero(fila[25]), control_objetivo_total=numero(fila[26]),
        control_objetivo_horas=numero(fila[24]),
        control_facturado_horas=numero(fila[27]), control_variable_productivo=numero(fila[28]),
        control_penalizaciones_bonos=numero(fila[29]), control_total_facturado=numero(fila[30]),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    registros = []
    for indice, fila in enumerate(libro[str(args.year)].iter_rows(min_row=3, max_col=31, values_only=True), 3):
        try:
            registro = fila_facturacion(fila, args.year)
        except ValueError as exc:
            raise ValueError(f'Hoja {args.year}, fila {indice}: {exc}') from exc
        if registro:
            registros.append(registro)
    app = create_app()
    with app.app_context():
        anteriores = Facturacion2026.query.filter(Facturacion2026.mes.like(f'{args.year}-%')).all()
        # El respaldo y el historial conservan las justificaciones anteriores;
        # no se adjudican a una fila nueva sin correspondencia inequívoca.
        archivo_anterior = [{'registro': item.to_dict(),
                             'justificaciones': [j.to_dict() for j in item.justificaciones]}
                            for item in anteriores if item.justificaciones]
        for item in anteriores:
            db.session.delete(item)
        db.session.flush()
        db.session.add_all(registros)
        db.session.flush()
        totales = defaultdict(float)
        for item in registros:
            totales[(item.mes, item.cliente)] += item.total_dashboard
        resumen = {'filas': len(registros), 'eliminadas': len(anteriores),
                   'sha256': hashlib.sha256(args.archivo.read_bytes()).hexdigest(),
                   'totales': [{'mes': m, 'cliente': c, 'importe': round(v, 2)} for (m,c),v in sorted(totales.items())]}
        if args.apply:
            db.session.add(HistorialCambio(accion='importacion', entidad='facturacion_anio', entidad_id=str(args.year),
                resumen=f'Reemplazo desde libro operativo: {len(registros)} filas',
                detalle=args.archivo.name, antes=json.dumps({'registros_con_justificaciones': archivo_anterior}, ensure_ascii=False),
                despues=json.dumps(resumen, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
