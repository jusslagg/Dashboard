"""Extrae del libro operativo las posiciones y vínculos de la hoja RESUMEN."""
import argparse
import json
import re
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('archivo', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'app/data/formato_resumen.json')
    args = p.parse_args()
    valores = load_workbook(args.archivo, read_only=True, data_only=True)
    formulas = load_workbook(args.archivo, read_only=True, data_only=False)
    tablas = {}
    for nombre in ('Facturacion Horas', 'Variable', 'Next Gen', 'Tarifacion', 'Unificado'):
        tablas[nombre] = {i: fila for i, fila in enumerate(valores[nombre].iter_rows(max_col=7, values_only=True), 1)}
    resumen_v = list(valores['RESUMEN'].iter_rows(max_col=25, values_only=True))
    resumen_f = list(formulas['RESUMEN'].iter_rows(max_col=7, values_only=True))
    conceptos = {'horas': 'Facturacion Horas', 'horas - backoffice': 'Facturacion Horas',
                 'variable productividad': 'Variable', 'next gen': 'Next Gen',
                 'tarifacion + otros': 'Tarifacion'}
    filas = []
    for numero in range(6, 258):
        row = resumen_v[numero - 1]
        site, concepto, nombre = row[2:5]
        formula = str(resumen_f[numero - 1][6] or '')
        c = str(concepto or '').strip().casefold()
        sheet = conceptos.get(c)
        links = []
        if sheet and 'SUMIF(' in formula.upper():
            buscada = (str(nombre or '') + str(site or '')).casefold()
            links = [(sheet, i) for i, f in tablas[sheet].items()
                     if i >= 5 and str(f[1] or '').casefold() == buscada]
        elif sheet or ('Unificado!' in formula and c == 'total'):
            for match in re.finditer(r"(?:'([^']+)'|([A-Za-z ]+))!\$?H\$?(\d+)", formula, re.I):
                origen = (match.group(1) or match.group(2)).strip()
                index = int(match.group(3))
                if origen in tablas and index in tablas[origen]:
                    links.append((origen, index))
        fuentes = []
        for origen, index in links:
            origen_fila = tablas[origen][index]
            # E contiene la clave que usa el libro para calcular esa apertura.
            fuentes.append({'tabla': origen, 'fila': index, 'cliente': origen_fila[2],
                            'operativa': origen_fila[4], 'servicio': origen_fila[6]})
        if str(nombre or '').strip().upper() == 'BI BANK':
            nombre = 'BIBANK'  # Grafía solicitada posteriormente para esta cuenta.
        # Solo los subtotales necesitan referencias a otras filas de RESUMEN.
        referencias = []
        if not sheet and not fuentes:
            for primero, ultimo in re.findall(r'G(\d+):G(\d+)', formula, re.I):
                referencias.extend(range(int(primero), int(ultimo) + 1))
            sin_rangos = re.sub(r'G\d+:G\d+', '', formula, flags=re.I)
            referencias.extend(int(n) for n in re.findall(r'G(\d+)', sin_rangos, re.I))
        filas.append({'fila': numero, 'site': site, 'concepto': concepto, 'campania': nombre,
                      'referencias': referencias, 'fuentes': fuentes})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    conocidas = sorted({str(f[4]).strip() for tabla in tablas.values() for f in tabla.values() if len(f) > 4 and f[4]})
    pares = {(str(f[2]).strip(), str(f[4]).strip()) for tabla in tablas.values() for f in tabla.values()
             if len(f) > 4 and f[2] and f[4]}
    for fila in valores['Matriz'].iter_rows(min_row=3, max_col=53, values_only=True):
        if fila[2] and fila[52]:
            pares.add((str(fila[2]).strip(), str(fila[52]).strip()))
    anotaciones = {str(i): fila[18] for i, fila in enumerate(resumen_v, 1)
                   if isinstance(fila[18], str) and fila[18]}
    comentarios = {str(i): fila[0] for i, fila in enumerate(resumen_v, 1)
                    if i != 5 and isinstance(fila[0], str) and fila[0]}
    apoyo = [{'fila': i, 'valores': list(resumen_v[i-1][20:24])} for i in range(5, 18)]
    args.output.write_text(json.dumps({'sheet': 'RESUMEN', 'filas': filas, 'operativas_conocidas': conocidas,
        'pares_conocidos': sorted(pares),
        'anotaciones': anotaciones, 'comentarios': comentarios, 'apoyo': apoyo}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(filas)} filas exportadas a {args.output}')


if __name__ == '__main__':
    main()
