"""Verifica que una Proforma rechazada explique la causa y la corrección."""
import io
import os
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree

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


def formulas_con_resultados(row):
    origen = excel([row])
    salida = io.BytesIO()
    with ZipFile(origen) as fuente, ZipFile(salida, 'w', ZIP_DEFLATED) as destino:
        for nombre in fuente.namelist():
            contenido = fuente.read(nombre)
            if nombre == 'xl/worksheets/sheet1.xml':
                root = ElementTree.fromstring(contenido)
                ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for referencia, valor in (('J2', '1000'), ('P2', '1055')):
                    celda = root.find(f'.//x:c[@r="{referencia}"]', ns)
                    celda.find('x:v', ns).text = valor
                contenido = ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)
            destino.writestr(nombre, contenido)
    salida.seek(0)
    return salida


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
    formulas_sin_resultado = valid_row()
    formulas_sin_resultado[9] = '=H2*I2'
    formulas_sin_resultado[15] = '=J2+O2'
    diagnostic(upload(excel([formulas_sin_resultado])), 'no tienen un resultado numérico guardado')

    success = upload(formulas_con_resultados(formulas_sin_resultado))
    assert success.status_code == 200, success.get_data(as_text=True)
    assert ProformaPersonal.query.count() == 1
    reemplazo_invalido = upload(excel([formulas_sin_resultado]))
    assert reemplazo_invalido.status_code == 400
    assert ProformaPersonal.query.count() == 1
    registro = ProformaPersonal.query.one()
    assert registro.monto_fijo == 1000 and registro.total_proyeccion == 1055
    print('OK: validaciones, fórmulas sin resultado guardado y conservación del lote anterior.')
