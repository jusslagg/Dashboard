"""Comprueba la sustitución proyectada→definitiva por tipo y período."""
from io import BytesIO
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


def archivo(periodo, negocio, horas):
    libro = Workbook()
    hoja = libro.active
    hoja.append(list(ENCABEZADOS_PROFORMA_PERSONAL))
    hoja.append(['FDV', periodo, negocio, 'CAT', f'Servicio {negocio}', '', 'NORMAL',
                 horas, 100, horas * 100, 0, 0, 0, 0, 0, horas * 100])
    contenido = BytesIO()
    libro.save(contenido)
    contenido.seek(0)
    return contenido


app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as cliente:
    usuario = Usuario(nombre='Prueba', email='transicion-proforma@example.test', rol='Admin',
                      puesto='Administrador', activo=True, debe_cambiar_password=False)
    usuario.set_password('Prueba12345')
    db.session.add(usuario)
    db.session.commit()
    with cliente.session_transaction() as sesion:
        sesion['usuario_id'] = usuario.id
        sesion['csrf_token'] = 'test-transicion'
    def importar(tipo, estado, periodo, negocio, horas):
        return cliente.post('/api/proforma-personal/importar', headers={'X-CSRF-Token': 'test-transicion'},
            data={'tipo_proforma': tipo, 'estado_proforma': estado,
                  'archivo': (archivo(periodo, negocio, horas), 'proforma.xlsx')})

    assert importar('Masivo', 'Proyectada', 202608, 'MASIVO', 100).status_code == 200
    assert importar('Soporte', 'Proyectada', 202608, 'SOPORTE', 20).status_code == 200
    assert importar('Masivo', 'Proyectada', 202609, 'MASIVO', 300).status_code == 200
    assert importar('Masivo', 'Definitiva', 202608, 'MASIVO', 110).status_code == 200
    datos = {(r.periodo, r.tipo_proforma): (r.estado_proforma, r.total_horas)
             for r in ProformaPersonal.query.all()}
    assert datos == {('202608', 'Masivo'): ('Definitiva', 110),
                     ('202608', 'Soporte'): ('Proyectada', 20),
                     ('202609', 'Masivo'): ('Proyectada', 300)}
    rechazo = importar('Masivo', 'Proyectada', 202608, 'MASIVO', 999)
    assert rechazo.status_code == 400
    assert ProformaPersonal.query.filter_by(periodo='202608', tipo_proforma='Masivo').one().total_horas == 110
    assert importar('Masivo', 'Definitiva', 202608, 'MASIVO', 115).status_code == 200
    assert ProformaPersonal.query.filter_by(periodo='202608', tipo_proforma='Masivo').one().total_horas == 115
    print('OK: definitiva reemplaza proyectada del mismo tipo y mes, conserva otros lotes y no admite retroceso accidental.')
