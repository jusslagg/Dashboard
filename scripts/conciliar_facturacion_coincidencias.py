"""Actualiza importes de filas con correspondencia única y verificable en el libro."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Facturacion2026, HistorialCambio, normalizar_jefe_site
from app.routes import normalizar_header
from scripts.reprocesar_facturacion_2026 import identidad_fuente, identidad_registro, periodo


def valor(fila, indice):
    dato = fila[indice]
    if dato is None or dato == '':
        return 0.0
    if isinstance(dato, bool) or not isinstance(dato, (int, float)) or not math.isfinite(dato):
        raise ValueError(f'Valor numérico inválido en columna {indice + 1}: {dato!r}')
    return float(dato)


def actualizar(registro, fila):
    indices = {
        'horas_objetivo': 10, 'horas_facturadas': 11, 'valor_hora': 12,
        'facturado_horas_manual': 13, 'tarifacion': 14,
        'variable_productivo': 17, 'netx_gen': 19, 'otros': 20,
        'total_facturado_manual': 21, 'variable_objetivo': 25,
        'control_objetivo_total': 26, 'control_facturado_horas': 27,
        'control_variable_productivo': 28, 'control_penalizaciones_bonos': 29,
        'control_total_facturado': 30,
    }
    valores = {campo: valor(fila, indice) for campo, indice in indices.items()}
    objetivo_vh = valor(fila, 22) or valores['valor_hora']
    objetivo_horas = valor(fila, 24)
    ajuste = valor(fila, 18)
    valores.update(valor_hora_objetivo=objetivo_vh, bonos=max(ajuste, 0),
                   penalizaciones=abs(min(ajuste, 0)))
    valores['objetivo_separar_ajuste_vh'] = bool(
        valores['horas_objetivo']
        and abs(objetivo_horas - valores['horas_objetivo'] * objetivo_vh) > .02
        and abs(objetivo_horas - valores['horas_objetivo'] * valores['valor_hora']) <= .02
    )
    for campo, dato in valores.items():
        setattr(registro, campo, dato)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    workbook = load_workbook(args.archivo, data_only=True, read_only=True)
    filas = [(i, fila) for i, fila in enumerate(
        workbook[str(args.year)].iter_rows(min_row=3, max_col=31, values_only=True), 3)
        if fila[4] and periodo(fila[9]).startswith(f'{args.year}-')]
    claves_fuente = Counter((periodo(f[9]), *identidad_fuente(f)) for _, f in filas)
    app = create_app()
    with app.app_context():
        registros = Facturacion2026.query.filter(
            Facturacion2026.mes.like(f'{args.year}-%'),
            Facturacion2026.es_next_gen.is_(False),
        ).all()
        claves_base = Counter((r.mes, *identidad_registro(r)) for r in registros)
        unicos = {(r.mes, *identidad_registro(r)): r for r in registros
                  if claves_base[(r.mes, *identidad_registro(r))] == 1}
        cambios, descartadas = [], Counter()
        for numero, fila in filas:
            clave = (periodo(fila[9]), *identidad_fuente(fila))
            registro = unicos.get(clave)
            if claves_fuente[clave] != 1 or registro is None:
                descartadas['sin_coincidencia_unica'] += 1
                continue
            jefe = str(fila[1] or '').strip()
            if not jefe or jefe.startswith('#') or normalizar_header(normalizar_jefe_site(jefe)) != normalizar_header(registro.jefe_site):
                descartadas['jefe_no_coincide_o_invalido'] += 1
                continue
            antes = registro.to_dict()
            try:
                actualizar(registro, fila)
            except ValueError:
                descartadas['valor_invalido'] += 1
                continue
            despues = registro.to_dict()
            if antes != despues:
                cambios.append({'id': registro.id, 'fila_excel': numero, 'antes': antes, 'despues': despues})
        resultado = {'fuente': args.archivo.name, 'sha256': hashlib.sha256(args.archivo.read_bytes()).hexdigest(),
                     'filas_fuente': len(filas), 'filas_modificadas': len(cambios),
                     'omitidas': dict(descartadas)}
        if args.apply:
            db.session.add(HistorialCambio(
                accion='reprocesamiento', entidad='facturacion_anio', entidad_id=str(args.year),
                resumen=f'Conciliación de coincidencias únicas: {len(cambios)} filas',
                detalle=json.dumps(resultado, ensure_ascii=False),
                antes=json.dumps({'cambios': cambios}, ensure_ascii=False, default=str),
                despues=json.dumps(resultado, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
