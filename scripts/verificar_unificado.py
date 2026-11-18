"""Compara la vista y la descarga de Unificado con el libro de origen."""
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
    args = parser.parse_args()
    libro = load_workbook(args.archivo, data_only=True, read_only=True)
    origen = libro['Unificado']
    filas = list(origen.iter_rows(min_row=5, max_row=93, max_col=21, values_only=True))
    app = create_app()
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    with app.app_context(), app.test_client() as client:
        user = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
        assert user
        with client.session_transaction() as session:
            session['usuario_id'] = user.id
        pantalla = client.get('/unificado')
        assert pantalla.status_code == 200 and b'/api/unificado' in pantalla.data
        response = client.get('/api/unificado?year=2026')
        assert response.status_code == 200
        data = response.get_json()
        descarga = client.get('/api/unificado/exportar?year=2026')
        assert descarga.status_code == 200
        hoja = load_workbook(BytesIO(descarga.data), data_only=True)['Unificado']
        diferencias = []
        comparados = 0
        for numero, fila_excel in enumerate(filas, 5):
            actual = data['filas'][numero - 5]
            assert actual['fila_excel'] == numero
            assert actual['clave_operativa'] == str(fila_excel[4]).replace('BI BANK', 'BIBANK')
            for mes in range(1, 13):
                esperado = fila_excel[6 + mes]
                if not isinstance(esperado, (int, float)):
                    continue
                comparados += 1
                valor = actual['meses'][f'2026-{mes:02d}']
                exportado = hoja.cell(numero, 7 + mes).value
                if abs(valor - esperado) > .03 or abs(exportado - esperado) > .03:
                    diferencias.append((numero, mes, esperado, valor, exportado))
        print(f'Unificado: {comparados} valores mensuales comparados; {len(diferencias)} diferencias')
        for diferencia in diferencias[:20]:
            print(diferencia)
        return 1 if diferencias else 0


if __name__ == '__main__':
    raise SystemExit(main())
