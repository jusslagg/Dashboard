import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from app import create_app, db
from app.models import HistorialCambio, ProformaPersonal

HEADERS = [
    'FDV', 'PERIODO', 'NEGOCIO', 'SITIO_PROVEEDOR', 'SEGMENTO', 'SUBSITIO',
    'TIPO_HORA', 'TOTAL_HORAS', 'PRECIO', 'MONTO_FIJO', 'PORCENTAJE_BONO_KPI_VS',
    'MONTO_VARIABLE_KPI_VS', 'PORCENTAJE_BONO_AC', 'MONTO_VARIABLE_AC',
    'MONTO_VARIABLE', 'TOTAL_PROYECCION',
]


def workbook(segmento, horas):
    book = Workbook()
    sheet = book.active
    sheet.append([])
    sheet.append(['PROYECCION'])
    sheet.append(HEADERS)
    sheet.append(['LOTE TEST', 202611, 'MASIVO', 'CAT', segmento, None, 'NORMAL', horas, 100, horas * 100, 0, 0, 0, 0, 0, horas * 100])
    result = io.BytesIO()
    book.save(result)
    return result.getvalue()


app = create_app()
with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['csrf_token'] = 'verificacion-lotes-proforma'
    with app.app_context():
        original_commit = db.session.commit
        db.session.commit = db.session.flush
        try:
            for nombre, segmento, horas in (
                ('lote-uno.xlsx', 'LOTE UNO TEST', 10),
                ('lote-dos.xlsx', 'LOTE DOS TEST', 20),
            ):
                response = client.post(
                    '/api/proforma-personal/importar',
                    data={'archivo': (io.BytesIO(workbook(segmento, horas)), nombre)},
                    headers={'X-CSRF-Token': 'verificacion-lotes-proforma'},
                    content_type='multipart/form-data',
                )
                assert response.status_code == 200, response.get_data(as_text=True)
            assert ProformaPersonal.query.filter_by(fdv='LOTE TEST', periodo='202611').count() == 2
            data = client.get('/api/proforma-personal?periodo=202611').get_json()
            lotes = [item for item in data['importaciones'] if item['archivo'] in ('lote-uno.xlsx', 'lote-dos.xlsx')]
            assert len(lotes) == 2
            assert all(item['filas'] == 1 and item['creadas'] == 1 and item['actualizadas'] == 0 for item in lotes)
            assert {item['archivo'] for item in lotes} == {'lote-uno.xlsx', 'lote-dos.xlsx'}
            print({'filas_acumuladas': 2, 'lotes_registrados': len(lotes), 'archivos': [item['archivo'] for item in lotes]})
        finally:
            db.session.rollback()
            db.session.commit = original_commit
