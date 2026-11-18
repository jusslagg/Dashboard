"""Conserva el objetivo de horas monetario de la columna Y del libro."""
import argparse
import json
from pathlib import Path
import sys
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Facturacion2026, HistorialCambio, _clave_nombre
from scripts.reemplazar_facturacion_libro import fila_facturacion


def clave(r):
    return (r.mes, *(_clave_nombre(str(x or '')) for x in
                     (r.cliente, r.campania, r.subcampania, r.tipo_jornada)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    fuentes = [registro for fila in libro[str(args.year)].iter_rows(min_row=3, max_col=31, values_only=True)
               if (registro := fila_facturacion(fila, args.year))]
    app = create_app()
    with app.app_context():
        actuales = Facturacion2026.query.filter(Facturacion2026.mes.like(f'{args.year}-%')).order_by(Facturacion2026.id).all()
        if len(fuentes) != len(actuales):
            raise ValueError('La cantidad de registros cambió: no se puede asociar el objetivo de forma segura')
        campos = ('horas_objetivo', 'horas_facturadas', 'valor_hora', 'total_facturado_manual', 'control_objetivo_total')
        for fuente, actual in zip(fuentes, actuales):
            if clave(fuente) != clave(actual) or any(abs(float(getattr(fuente, x) or 0) - float(getattr(actual, x) or 0)) > .011 for x in campos):
                raise ValueError(f'La fila {actual.id} cambió: no se puede asociar el objetivo de forma segura')
        for fuente, actual in zip(fuentes, actuales):
            actual.control_objetivo_horas = fuente.control_objetivo_horas
            actual.mes_apertura_origen = fuente.mes_apertura_origen
        if args.apply:
            db.session.add(HistorialCambio(accion='importacion', entidad='facturacion_anio', entidad_id=str(args.year),
                resumen=f'Objetivos de facturación por horas desde columna Y: {len(actuales)} filas',
                detalle=args.archivo.name, despues=json.dumps({'filas': len(actuales)}, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        print(f'{len(actuales)} objetivos {"guardados" if args.apply else "validados"}')


if __name__ == '__main__':
    main()
