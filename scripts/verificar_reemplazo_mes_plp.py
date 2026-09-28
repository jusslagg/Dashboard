"""Verifica que un pegado mensual PLP reemplace la foto completa del mes."""
from inspect import unwrap
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask

from app import db
from app.models import HistorialCambio, ProyeccionMatriz
from app.routes import api_edicion_masiva_proyecciones_plp


def proyeccion(campania, mes, horas):
    return ProyeccionMatriz(
        cliente='Personal', campania=campania, year=int(mes[:4]), mes=mes,
        tipo_plp='Personal', horas_carga_manual=True,
        carga_semanal='L a V', carga_horaria=6, dias_objetivo=20,
        dotacion_requerida=horas / 120, horas_requeridas=horas,
        horas_requeridas_manual=horas, porcentaje_cumplimiento=100,
    )


def fila(campania, mes, horas, registro_id=None):
    return {
        'id': registro_id, 'tipo_plp': 'Personal', 'mes': mes,
        'campania': campania, 'horas': horas, 'carga_semanal': 'L a V',
        'carga_horaria': 6, 'porcentaje_cumplimiento': 100,
    }


class ReemplazoMesPLPTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', DEFAULT_YEAR=2026, TESTING=True)
        db.init_app(self.app)
        self.app.add_url_rule(
            '/api/proyecciones-plp/edicion-masiva',
            view_func=unwrap(api_edicion_masiva_proyecciones_plp), methods=['POST'],
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            proyeccion('ABONOS', '2026-10', 100),
            proyeccion('ANTERIOR', '2026-10', 200),
            proyeccion('OTRO MES', '2026-11', 300),
        ])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_reemplaza_solo_el_mes_informado(self):
        abonos = ProyeccionMatriz.query.filter_by(campania='ABONOS').one()
        response = self.client.post('/api/proyecciones-plp/edicion-masiva', json={
            'year': 2026,
            'reemplazar_meses': ['2026-10'],
            'filas': [
                fila('ABONOS', '2026-10', 150, abonos.id),
                fila('NUEVA', '2026-10', 50),
            ],
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        octubre = ProyeccionMatriz.query.filter_by(mes='2026-10').order_by(ProyeccionMatriz.campania).all()
        self.assertEqual([(item.campania, item.horas_requeridas) for item in octubre], [('ABONOS', 150), ('NUEVA', 50)])
        self.assertEqual(ProyeccionMatriz.query.filter_by(mes='2026-11', campania='OTRO MES').count(), 1)
        self.assertEqual(len(response.json['eliminadas']), 1)
        self.assertEqual(response.json['meses_reemplazados'], ['2026-10'])
        self.assertIn('Reemplazo PLP 2026-10', HistorialCambio.query.one().resumen)

    def test_edicion_manual_no_elimina_ausentes(self):
        abonos = ProyeccionMatriz.query.filter_by(campania='ABONOS').one()
        response = self.client.post('/api/proyecciones-plp/edicion-masiva', json={
            'year': 2026, 'filas': [fila('ABONOS', '2026-10', 175, abonos.id)],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProyeccionMatriz.query.filter_by(mes='2026-10').count(), 2)
        self.assertEqual(ProyeccionMatriz.query.filter_by(campania='ANTERIOR').count(), 1)


if __name__ == '__main__':
    unittest.main()
