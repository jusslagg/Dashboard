"""Compara por cliente, campaña y mes los importes de Facturación contra el libro."""
import argparse
from collections import defaultdict
from pathlib import Path
import sys

from openpyxl import load_workbook
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Facturacion2026, _clave_nombre
from scripts.reemplazar_facturacion_libro import fila_facturacion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    args = parser.parse_args()
    campos = ('horas_objetivo', 'horas_facturadas', 'facturado_horas_manual',
              'variable_productivo', 'netx_gen', 'total_facturado_manual',
              'control_objetivo_total', 'control_total_facturado')
    esperado = defaultdict(lambda: [0.0] * len(campos))
    actual = defaultdict(lambda: [0.0] * len(campos))
    def sumar(destino, registro):
        clave = (registro.mes, *(_clave_nombre(str(x or '')) for x in
                                (registro.cliente, registro.campania, registro.subcampania)))
        for i, campo in enumerate(campos):
            destino[clave][i] += getattr(registro, campo) or 0
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    for fila in libro[str(args.year)].iter_rows(min_row=3, max_col=31, values_only=True):
        registro = fila_facturacion(fila, args.year)
        if registro:
            sumar(esperado, registro)
    app = create_app()
    with app.app_context():
        for registro in Facturacion2026.query.filter(Facturacion2026.mes.like(f'{args.year}-%')).all():
            sumar(actual, registro)
    diferencias = []
    for clave in sorted(set(esperado) | set(actual)):
        for i, campo in enumerate(campos):
            if abs(esperado[clave][i] - actual[clave][i]) > .03:
                diferencias.append((clave, campo, esperado[clave][i], actual[clave][i]))
    print(f'{len(set(esperado) | set(actual))} combinaciones; {len(diferencias)} diferencias')
    for detalle in diferencias[:50]:
        print(detalle)
    return 1 if diferencias else 0


if __name__ == '__main__':
    raise SystemExit(main())
