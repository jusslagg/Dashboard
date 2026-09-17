"""Verifica que una Proforma rechazada explique la causa y la corrección."""
import io
import os
from pathlib import Path
import sys

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from app import create_app, db
from app.models import ProformaPersonal, Usuario
from app.routes import ENCABEZADOS_PROFORMA_PERSONAL


def excel(rows, headers=ENCABEZADOS_PROFORMA_PERSONAL):
    book = Workbook()
    sheet = book.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


def valid_row(segment='Campaña', business='MASIVO', period=202609, hours=10):
    return ['FDV', period, business, 'CAT', segment, '', 'NORMAL', hours,
            100, 1000, 5, 50, 0.5, 5, 55, 1055]


app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as client:
    user = Usuario(nombre='Prueba', email='errores-proforma@example.test', rol='Admin',
                   puesto='Administrador', activo=True, debe_cambiar_password=False)
    user.set_password('Prueba12345')
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'errores-proforma'
    headers_http = {'X-CSRF-Token': 'errores-proforma'}

    def upload(content, selected='Masivo', name='proforma.xlsx'):
        return client.post('/api/proforma-personal/importar', headers=headers_http,
                           data={'tipo_proforma': selected, 'estado_proforma': 'Proyectada', 'archivo': (content, name)},
                           content_type='multipart/form-data')

    def diagnostic(response, expected):
        assert response.status_code == 400, response.get_data(as_text=True)
        data = response.get_json()
        assert data['diagnostico']['causa'] and data['diagnostico']['correccion']
        complete = ' '.join([data['diagnostico']['causa'], data['diagnostico']['correccion'],
                             *data['diagnostico']['detalles']])
        assert expected in complete, complete
        assert ProformaPersonal.query.count() == 0

    bad_headers = list(ENCABEZADOS_PROFORMA_PERSONAL)
    bad_headers[1] = 'MES INVENTADO'
    diagnostic(upload(excel([valid_row()], bad_headers)), 'columna B')
    diagnostic(upload(excel([valid_row(period='período desconocido')])), 'AAAAMM')
    numeric = valid_row()
    numeric[7] = 'diez horas'
    diagnostic(upload(excel([numeric])), 'H (TOTAL_HORAS)')
    diagnostic(upload(excel([valid_row(), valid_row()])), 'repite la misma combinación')
    diagnostic(upload(excel([valid_row(), valid_row('Soporte', 'SOPORTE')])), 'mezcla tipos')
    diagnostic(upload(excel([valid_row()]), selected='Personal Pay'), 'columna NEGOCIO')
    diagnostic(upload(io.BytesIO(b'broken workbook')), 'no se pudo abrir')

    success = upload(excel([valid_row()]))
    assert success.status_code == 200, success.get_data(as_text=True)
    assert ProformaPersonal.query.count() == 1
    print('OK: cabecera, período, número, duplicado, mezcla, selector y archivo dañado explican causa y corrección.')
