"""Compara la apertura mensual de Directorio con la hoja del libro operativo."""
import argparse
from pathlib import Path
import sys
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.routes import construir_apertura_desvios_clientes, normalizar_header


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    hoja = next(hoja for hoja in libro if normalizar_header(hoja.title) == 'apertura desvios por cliente')
    filas = list(hoja.iter_rows(max_col=14, values_only=True))
    app = create_app()
    with app.app_context():
        datos = construir_apertura_desvios_clientes(args.year)['filas']
    por_clave = {(normalizar_header(item['cliente']), item['mes']): item for item in datos}
    actualizado = por_clave.get(('assurant', '2026-08'))
    actualizado = bool(args.year == 2026 and actualizado and not actualizado.get('fuente_parcial'))
    conceptos = ('cumplimiento_horas', 'valor_hora', 'cumplimiento_facturacion', 'horas',
                 'variable', 'bonos_penalizaciones', 'porcentaje_desvio', 'total')
    errores, comparados = [], 0
    for inicio in range(3, 235, 8):
        cliente = filas[inicio][0]
        if not cliente:
            continue
        for mes in range(1, 13):
            actual = por_clave.get((normalizar_header(cliente), f'{args.year}-{mes:02d}'))
            for indice, campo in enumerate(conceptos):
                if actualizado and mes == 8 and normalizar_header(cliente) in ('assurant', 'total general'):
                    continue  # Agosto fue actualizado con la fila suministrada después del libro.
                esperado = filas[inicio + indice][mes + 1]
                valor = actual[campo] if actual else None
                if actual and actual.get('fuente_parcial') and esperado is None:
                    continue  # Es una recuperación identificada, ausente en la hoja actual.
                if esperado is None and valor is None:
                    continue
                comparados += 1
                tolerancia = .02 if indice in (3, 4, 5, 7) else 1e-8
                if not isinstance(esperado, (int, float)) or valor is None or abs(esperado - valor) > tolerancia:
                    errores.append((cliente, mes, campo, esperado, valor))
    print(f'Apertura: {comparados} valores comparados; {len(errores)} diferencias')
    for error in errores[:40]:
        print(error)
    return 1 if errores else 0


if __name__ == '__main__':
    raise SystemExit(main())
