import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from app import create_app, db
from app.models import HistorialCambio, ProformaPersonal

headers = [
    'FDV', 'PERIODO', 'NEGOCIO', 'SITIO_PROVEEDOR', 'SEGMENTO', 'SUBSITIO',
    'TIPO_HORA', 'TOTAL_HORAS', 'PRECIO', 'MONTO_FIJO', 'PORCENTAJE_BONO_KPI_VS',
    'MONTO_VARIABLE_KPI_VS', 'PORCENTAJE_BONO_AC', 'MONTO_VARIABLE_AC',
    'MONTO_VARIABLE', 'TOTAL_PROYECCION',
]
book = Workbook()
sheet = book.active
sheet.append([])
sheet.append(['PROYECCION'])
sheet.append(headers)
sheet.append(['TEST FDV', 202612, 'MASIVO', 'CAT', 'EXISTENTE TEST', None, 'NORMAL', 20, 100, 2000, 5, 100, 0.5, 10, 110, 2110])
sheet.append(['TEST FDV', 202612, 'MASIVO', 'CAT', 'NUEVA TEST', None, 'NORMAL', 30, 100, 3000, 0, 0, 0, 0, 0, 3000])
content = io.BytesIO()
book.save(content)

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['csrf_token'] = 'verificacion-undo-proforma'
    with app.app_context():
        original = ProformaPersonal(
            fdv='TEST FDV', periodo='202612', negocio='MASIVO', sitio_proveedor='CAT',
            segmento='EXISTENTE TEST', subsitio=None, tipo_hora='NORMAL', total_horas=10,
            precio=100, monto_fijo=1000, porcentaje_bono_kpi_vs=0,
            monto_variable_kpi_vs=0, porcentaje_bono_ac=0, monto_variable_ac=0,
            monto_variable=0, total_proyeccion=1000, bono_porcentaje_total=0,
        )
        db.session.add(original)
        db.session.flush()
        original_id = original.id
        original_commit = db.session.commit
        db.session.commit = db.session.flush
        try:
            response = client.post(
                '/api/proforma-personal/importar',
                data={'archivo': (io.BytesIO(content.getvalue()), 'proforma-test.xlsx')},
                headers={'X-CSRF-Token': 'verificacion-undo-proforma'},
                content_type='multipart/form-data',
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            history = HistorialCambio.query.filter_by(entidad='proforma_personal').order_by(HistorialCambio.id.desc()).first()
            assert history is not None
            assert db.session.get(ProformaPersonal, original_id).total_horas == 20
            assert ProformaPersonal.query.filter_by(segmento='NUEVA TEST').count() == 1
            undone = client.post(
                f'/api/historial/{history.id}/deshacer',
                headers={'X-CSRF-Token': 'verificacion-undo-proforma'},
            )
            assert undone.status_code == 200, undone.get_data(as_text=True)
            assert db.session.get(ProformaPersonal, original_id).total_horas == 10
            assert ProformaPersonal.query.filter_by(segmento='NUEVA TEST').count() == 0
            print({'importar': response.status_code, 'deshacer': undone.status_code, 'mensaje': undone.get_json()['mensaje']})
        finally:
            db.session.rollback()
            db.session.commit = original_commit
