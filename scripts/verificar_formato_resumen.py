"""Contrasta posiciones, rótulos e importes exportados contra RESUMEN."""
import argparse
from io import BytesIO
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Usuario


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    parser.add_argument('--year', type=int, default=2026)
    parser.add_argument('--completo', action='store_true', help='Comprueba también ambas hojas del libro integral')
    args = parser.parse_args()
    origen = load_workbook(args.archivo, read_only=True, data_only=True)
    fuente = list(origen['RESUMEN'].iter_rows(max_row=262, max_col=25, values_only=True))
    app = create_app()
    with app.app_context():
        usuario = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
        if not usuario:
            raise RuntimeError('No existe un usuario activo con acceso al resumen')
        usuario_id = usuario.id
    with app.test_client() as cliente:
        with cliente.session_transaction() as session:
            session['usuario_id'] = usuario_id
        respuesta = cliente.get(f'/api/resumen-proyeccion/exportar?year={args.year}')
        assert respuesta.status_code == 200, respuesta.get_data(as_text=True)
        libro = load_workbook(BytesIO(respuesta.data), data_only=True)
        assert libro.sheetnames == ['RESUMEN']
        hoja = libro['RESUMEN']
        errores = []
        def comparar(fila, columna, esperado, tolerancia=.03):
            actual = hoja.cell(fila, columna).value
            if isinstance(esperado, (int, float)) and not isinstance(esperado, bool):
                if not isinstance(actual, (int, float)) or abs(actual-esperado) > tolerancia:
                    errores.append((hoja.cell(fila, columna).coordinate, esperado, actual))
            elif (actual or None) != (esperado or None):
                errores.append((hoja.cell(fila, columna).coordinate, esperado, actual))

        for fila in (2, 3, 4, 5, *range(6, 258), 260, 261, 262):
            for columna in range(1, 19):
                esperado = fuente[fila-1][columna-1]
                if fila == 5 and columna == 6:
                    esperado = args.year
                if columna == 5 and esperado == 'BI BANK':
                    esperado = 'BIBANK'  # Grafía confirmada por el usuario.
                comparar(fila, columna, esperado)
        for fila in range(5, 18):
            for columna in range(21, 26):
                comparar(fila, columna, fuente[fila-1][columna-1])
        for fila in range(1, 263):
            esperado = fuente[fila-1][18]
            if fila == 61 and isinstance(esperado, str) and esperado.lower() == 'bibank':
                esperado = 'BIBANK'
            comparar(fila, 19, esperado)
        comparar(2, 20, fuente[1][19])
        api = cliente.get(f'/api/resumen-proyeccion?year={args.year}')
        assert api.status_code == 200
        filas_api = api.get_json()['filas_resumen']
        assert [fila['fila_excel'] for fila in filas_api[:253]] == [4] + list(range(6, 258))
        if args.completo:
            integral = cliente.get(f'/proyectados/exportar.xlsx?year={args.year}')
            assert integral.status_code == 200
            completo = load_workbook(BytesIO(integral.data), data_only=True)
            for nombre in ('Facturación horas', 'RESUMEN'):
                assert nombre in completo.sheetnames, f'Falta la hoja {nombre}'
                otra = completo[nombre]
                for fila in range(1, 263):
                    for columna in range(1, 26):
                        if hoja.cell(fila, columna).value != otra.cell(fila, columna).value:
                            errores.append((f'{nombre}!{otra.cell(fila, columna).coordinate}',
                                            hoja.cell(fila, columna).value, otra.cell(fila, columna).value))
        print(f'Formato RESUMEN: {len(errores)} diferencias en posiciones, nombres y valores')
        for error in errores[:30]:
            print(error)
        return 1 if errores else 0


if __name__ == '__main__':
    raise SystemExit(main())
