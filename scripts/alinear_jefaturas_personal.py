"""Aplica la distribución de jefaturas de Personal a altas y facturación."""
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio, normalizar_jefe_site
from app.routes import jefe_personal_por_servicio, normalizar_header


def jefe(registro):
    # El grupo SMB y Soporte prevalece incluso si el servicio dice Ventas.
    # Dentro de CX, el segmento y el nombre identifican Retención, Ventas y GCR.
    return normalizar_jefe_site(jefe_personal_por_servicio(
        registro.tipo_negocio, getattr(registro, 'segmento', ''),
        registro.campania, registro.subcampania,
    ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        altas = AsignacionComercial.query.filter(
            AsignacionComercial.cliente.ilike('personal%'), AsignacionComercial.activa.is_(True),
        ).all()
        cambios_altas = []
        por_identidad = {}
        for alta in altas:
            nuevo = jefe(alta)
            identidad = tuple(normalizar_header(x) for x in (alta.tipo_negocio, alta.campania, alta.subcampania))
            por_identidad.setdefault(identidad, set()).add(nuevo)
            if alta.jefe_site != nuevo:
                cambios_altas.append({'id': alta.id, 'antes': alta.jefe_site, 'despues': nuevo})
                alta.jefe_site = nuevo
        cambios_facturas, sin_alta = [], Counter()
        facturas = Facturacion2026.query.filter(Facturacion2026.cliente.ilike('personal%')).all()
        for fila in facturas:
            identidad = tuple(normalizar_header(x) for x in (fila.tipo_negocio, fila.campania, fila.subcampania))
            candidatos = por_identidad.get(identidad, set())
            if len(candidatos) != 1:
                sin_alta[identidad] += 1
                continue
            nuevo = next(iter(candidatos))
            if fila.jefe_site != nuevo:
                cambios_facturas.append({'id': fila.id, 'antes': fila.jefe_site, 'despues': nuevo})
                fila.jefe_site = nuevo
        resultado = {'altas_actualizadas': len(cambios_altas), 'facturas_actualizadas': len(cambios_facturas),
                     'facturas_sin_alta_unica': sum(sin_alta.values()),
                     'identidades_sin_alta': [{'tipo': k[0], 'campania': k[1], 'subcampania': k[2], 'filas': v}
                                              for k, v in sorted(sin_alta.items())]}
        if args.apply:
            db.session.add(HistorialCambio(accion='edicion', entidad='asignaciones_personal', entidad_id='jefaturas',
                resumen='Distribución de jefaturas de Personal desde altas',
                antes=json.dumps({'altas': cambios_altas, 'facturas': cambios_facturas}, ensure_ascii=False),
                despues=json.dumps(resultado, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
