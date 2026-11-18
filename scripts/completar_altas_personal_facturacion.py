"""Incorpora en Altas servicios de Personal presentes en Facturación."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, HistorialCambio, _clave_nombre, normalizar_gerente, normalizar_jefe_site
from app.routes import jefe_personal_por_servicio, obtener_o_crear_campania, segmento_personal_por_servicio
from scripts.reprocesar_facturacion_2026 import periodo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    fuentes = defaultdict(list)
    for fila in libro[str(args.year)].iter_rows(min_row=3, max_col=10, values_only=True):
        if _clave_nombre(str(fila[4] or '')) != 'personal' or not fila[7] or not periodo(fila[9]).startswith(f'{args.year}-'):
            continue
        fuentes[_clave_nombre(str(fila[7]))].append(fila)
    app = create_app()
    with app.app_context():
        altas = AsignacionComercial.query.filter(
            AsignacionComercial.cliente.ilike('personal%'), AsignacionComercial.activa.is_(True)).all()
        existentes = {_clave_nombre(x.subcampania) for x in altas}
        nuevas, omitidas = [], []
        for clave, filas in fuentes.items():
            if clave in existentes:
                continue
            grupos = {_clave_nombre(str(f[6] or '')) for f in filas}
            gerentes = {normalizar_gerente(str(f[5])) for f in filas if f[5] and not str(f[5]).startswith('#')}
            if len(grupos) != 1 or len(gerentes) != 1:
                omitidas.append(str(filas[0][7]).strip())
                continue
            grupo = next(iter(grupos))
            tipo = {'personal': 'Personal CX', 'personalcx': 'Personal CX',
                    'personalsoporte': 'Personal Soporte', 'personalsmb': 'Personal SMB'}.get(grupo)
            if not tipo:
                omitidas.append(str(filas[0][7]).strip())
                continue
            nombre = str(filas[0][7]).strip()
            segmento = segmento_personal_por_servicio(nombre, tipo)
            if not segmento and tipo == 'Personal CX':
                segmento = 'Customer'
            registro = AsignacionComercial(
                cliente='Personal', gerente=next(iter(gerentes)),
                jefe_site=normalizar_jefe_site(jefe_personal_por_servicio(tipo, nombre)),
                campania=nombre, subcampania=nombre, tipo_negocio=tipo,
                segmento=segmento,
                grupo_facturacion='Personal', es_next_gen=False, activa=True,
                campania_catalogo=obtener_o_crear_campania('Personal', nombre),
            )
            db.session.add(registro)
            db.session.flush()
            nuevas.append(registro.to_dict())
        resultado = {'nuevas': nuevas, 'omitidas': omitidas}
        if args.apply:
            db.session.add(HistorialCambio(accion='importacion', entidad='asignaciones_personal', entidad_id=str(args.year),
                resumen=f'Altas de Personal desde Facturación: {len(nuevas)} servicios',
                detalle=args.archivo.name, despues=json.dumps(resultado, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
