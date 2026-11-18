"""Incorpora al maestro las identidades comerciales presentes en Facturación."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, HistorialCambio, _clave_nombre, normalizar_gerente, normalizar_jefe_site
from app.routes import inferir_grupo_facturacion, obtener_o_crear_campania
from scripts.reprocesar_facturacion_2026 import periodo


def clave(*valores):
    return tuple(_clave_nombre(str(valor or '')) for valor in valores)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    por_identidad = defaultdict(list)
    for fila in libro[str(args.year)].iter_rows(min_row=3, max_col=31, values_only=True):
        if not fila[4] or clave(fila[4]) == ('personal',) or not fila[6] or not fila[7]:
            continue
        if periodo(fila[9]).startswith(f'{args.year}-'):
            por_identidad[clave(fila[4], fila[6], fila[7])].append(fila)
    app = create_app()
    with app.app_context():
        altas = AsignacionComercial.query.filter_by(activa=True).all()
        existentes = {clave(a.cliente, a.campania, a.subcampania) for a in altas}
        nuevas, omitidas = [], []
        for identidad, filas in por_identidad.items():
            if identidad in existentes:
                continue
            mes = max(periodo(f[9]) for f in filas)
            recientes = [f for f in filas if periodo(f[9]) == mes]
            responsables = {(normalizar_gerente(str(f[5] or '').strip()), normalizar_jefe_site(str(f[1] or '').strip()))
                            for f in recientes if str(f[5] or '').strip() not in ('', '0', '#N/A')
                            and str(f[1] or '').strip() not in ('', '0', '#N/A')}
            if len(responsables) > 1:
                omitidas.append({'cliente': recientes[0][4], 'campania': recientes[0][6],
                                  'subcampania': recientes[0][7], 'mes': mes,
                                  'motivo': 'responsables no únicos'})
                continue
            fila = recientes[0]
            cliente, campania, subcampania = (str(fila[i]).strip() for i in (4, 6, 7))
            # El libro expresa algunos responsables como 0. La opción explícita
            # mantiene disponible el servicio sin asignar una persona supuesta.
            if responsables:
                gerente, jefe = next(iter(responsables))
            else:
                gerentes = {normalizar_gerente(str(f[5]).strip()) for f in recientes
                            if str(f[5] or '').strip() not in ('', '0', '#N/A')}
                jefes = {normalizar_jefe_site(str(f[1]).strip()) for f in recientes
                         if str(f[1] or '').strip() not in ('', '0', '#N/A')}
                if len(gerentes) > 1 or len(jefes) > 1:
                    omitidas.append({'cliente': fila[4], 'campania': fila[6],
                                      'subcampania': fila[7], 'mes': mes,
                                      'motivo': 'responsables no únicos'})
                    continue
                gerente, jefe = next(iter(gerentes), 'Sin asignar'), next(iter(jefes), 'Sin asignar')
            alta = AsignacionComercial(
                cliente=cliente, gerente=gerente, jefe_site=jefe, campania=campania, subcampania=subcampania,
                grupo_facturacion=inferir_grupo_facturacion(cliente, campania),
                campania_catalogo=obtener_o_crear_campania(cliente, campania), activa=True, es_next_gen=False,
            )
            db.session.add(alta)
            db.session.flush()
            existentes.add(identidad)
            nuevas.append(alta.to_dict())
        resultado = {'altas_creadas': len(nuevas), 'omitidas': omitidas, 'altas': nuevas}
        if args.apply:
            db.session.add(HistorialCambio(accion='importacion', entidad='asignaciones_facturacion', entidad_id=str(args.year),
                resumen=f'Altas desde Facturación: {len(nuevas)} servicios', detalle=args.archivo.name,
                despues=json.dumps(resultado, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
