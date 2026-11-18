"""Da de alta los servicios de Personal publicados por el libro de proyección."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, HistorialCambio, _clave_nombre, normalizar_gerente, normalizar_jefe_site
from app.routes import jefe_personal_por_servicio, normalizar_header, obtener_o_crear_campania, segmento_personal_por_servicio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    tipos = {'personal': 'Personal CX', 'personal cx': 'Personal CX',
             'personal soporte': 'Personal Soporte', 'personal smb': 'Personal SMB'}
    gerencias = defaultdict(set)
    for fila in libro['Facturacion Horas'].iter_rows(min_row=5, max_col=7, values_only=True):
        grupo = normalizar_header(fila[2])
        gerente = str(fila[3] or '').strip()
        if grupo in tipos and gerente:
            gerencias[grupo].add(normalizar_gerente(gerente))
    servicios = {}
    for fila in libro['Desglose HORAS PERSONAL'].iter_rows(min_row=2, max_col=4, values_only=True):
        grupo, fecha, nombre = normalizar_header(fila[0]), fila[1], str(fila[2] or '').strip()
        if grupo not in tipos or getattr(fecha, 'year', None) != args.year or not nombre:
            continue
        tipo = tipos[grupo]
        if tipo == 'Personal CX' and ('personal pay' in normalizar_header(nombre) or 'ppay' in normalizar_header(nombre)):
            tipo = 'Personal PPAY'
        servicios.setdefault((tipo, _clave_nombre(nombre)), (grupo, nombre))
    app = create_app()
    with app.app_context():
        altas = AsignacionComercial.query.filter(
            AsignacionComercial.cliente.ilike('personal%'), AsignacionComercial.activa.is_(True)).all()
        existentes = {(a.tipo_negocio, _clave_nombre(a.subcampania)) for a in altas}
        nuevas, omitidas = [], []
        for (tipo, clave), (grupo, nombre) in servicios.items():
            if (tipo, clave) in existentes:
                continue
            if len(gerencias[grupo]) != 1:
                omitidas.append({'grupo': grupo, 'servicio': nombre, 'motivo': 'gerencia no única en el libro'})
                continue
            segmento = segmento_personal_por_servicio(nombre, tipo)
            if not segmento and tipo == 'Personal CX':
                segmento = 'Customer'
            jefe = normalizar_jefe_site(jefe_personal_por_servicio(tipo, segmento, nombre))
            alta = AsignacionComercial(
                cliente='Personal', gerente=next(iter(gerencias[grupo])), jefe_site=jefe,
                campania=nombre, subcampania=nombre, tipo_negocio=tipo, segmento=segmento,
                grupo_facturacion='Personal', es_next_gen=False, activa=True,
                campania_catalogo=obtener_o_crear_campania('Personal', nombre),
            )
            db.session.add(alta)
            db.session.flush()
            existentes.add((tipo, clave))
            nuevas.append(alta.to_dict())
        resultado = {'altas_creadas': len(nuevas), 'omitidas': omitidas, 'altas': nuevas}
        if args.apply:
            db.session.add(HistorialCambio(accion='importacion', entidad='asignaciones_personal', entidad_id=str(args.year),
                resumen=f'Altas de Personal desde Proyectados: {len(nuevas)} servicios',
                detalle=args.archivo.name, despues=json.dumps(resultado, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
