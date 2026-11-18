"""Extrae las identidades y el orden de la hoja Unificado de proyectados."""
import argparse
import json
from pathlib import Path
from openpyxl import load_workbook


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    hoja = libro['Unificado']
    filas = []
    for numero, valores in enumerate(hoja.iter_rows(min_row=5, max_row=hoja.max_row,
                                                     max_col=7, values_only=True), 5):
        if not valores[4]:
            continue
        textos = [v if isinstance(v, str) else '' if v is None else str(v) for v in valores]
        # El usuario indicó esta grafía para todo el circuito.
        textos = [v.replace('BI BANK', 'BIBANK') for v in textos]
        filas.append({'fila_excel': numero, 'cliente_proyectado': textos[0],
                      'clave_agrupacion': textos[1], 'cliente': textos[2], 'site': textos[3],
                      'clave_operativa': textos[4], 'segmento': textos[5], 'campania': textos[6]})
    destino = Path(__file__).resolve().parents[1] / 'app/data/formato_unificado.json'
    destino.write_text(json.dumps(filas, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(filas)} filas guardadas en {destino}')


if __name__ == '__main__':
    main()
