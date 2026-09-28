"""Verifica que el libro operativo preserve decimales y reemplace meses PLP."""
from inspect import unwrap
from io import BytesIO
from pathlib import Path
import sys
import unittest

from flask import Flask
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.models import ProyeccionMatriz
from app.routes import api_importar_proyecciones_plp


def proyeccion(campania, mes, horas):
    return ProyeccionMatriz(
        cliente='Personal', campania=campania, year=int(mes[:4]), mes=mes,
        tipo_plp='Personal', horas_carga_manual=True, carga_semanal='L a V',
        carga_horaria=6, dias_objetivo=20, dotacion_requerida=horas / 120,
        horas_requeridas=horas, porcentaje_cumplimiento=97,
    )


def libro_operativo():
    libro = Workbook()
    matriz = libro.active
    matriz.title = 'Matriz'
    matriz.append([None] * 15)
    matriz.append([None] * 15)
    fila = [None] * 15
    total = 10518.5 + 3456.125
    fila[2], fila[3], fila[5], fila[10], fila[11], fila[14] = (
        'Personal', 'Personal', __import__('datetime').datetime(2026, 10, 1), total, total * .98, .98,
    )
    matriz.append(fila)
    auxiliar = libro.create_sheet('Desglose HORAS PERSONAL')
    auxiliar.append(['Clasificación', 'Mes', 'Campaña', 'Horas'])
    auxiliar.append(['Personal', __import__('datetime').datetime(2026, 10, 1), 'ABONOS', 10518.5])
    auxiliar.append(['Personal', __import__('datetime').datetime(2026, 10, 1), 'NUEVA', 3456.125])
    auxiliar.append(['Personal', __import__('datetime').datetime(2026, 10, 1), 'CERO', 0])
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


class ImportacionLibroPLPTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', DEFAULT_YEAR=2026, TESTING=True)
        db.init_app(self.app)
        self.app.add_url_rule(
            '/api/proyecciones-plp/importar',
            view_func=unwrap(api_importar_proyecciones_plp), methods=['POST'],
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            proyeccion('ABONOS', '2026-10', 1),
            proyeccion('ANTERIOR', '2026-10', 2),
            proyeccion('OTRO MES', '2026-11', 3),
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_preserva_precision_y_reemplaza_mes(self):
        respuesta = self.app.test_client().post(
            '/api/proyecciones-plp/importar',
            data={'year': '2026', 'archivo': (BytesIO(libro_operativo()), 'proyeccion.xlsx')},
            content_type='multipart/form-data',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.get_data(as_text=True))
        self.assertEqual(respuesta.json['origen'], 'libro_operativo')
        octubre = ProyeccionMatriz.query.filter_by(mes='2026-10').order_by(ProyeccionMatriz.campania).all()
        self.assertEqual([fila.campania for fila in octubre], ['ABONOS', 'NUEVA'])
        self.assertEqual(octubre[0].horas_requeridas, 10518.5)
        self.assertEqual(octubre[1].horas_requeridas, 3456.125)
        self.assertEqual(octubre[0].porcentaje_cumplimiento, 98)
        self.assertEqual(ProyeccionMatriz.query.filter_by(mes='2026-11', campania='OTRO MES').count(), 1)
        self.assertEqual(respuesta.json['eliminadas'], 1)


if __name__ == '__main__':
    unittest.main()
