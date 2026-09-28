"""Prueba el guardado múltiple con SQLite en memoria, sin modificar datos reales."""
from inspect import unwrap
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from app import db
from app.models import Campania, NormalizacionNombreProyectado, HistorialCambio
from app.routes import api_normalizaciones_proyectados, api_eliminar_normalizacion_proyectados


class NormalizacionesLoteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', DEFAULT_YEAR=2026, TESTING=True)
        db.init_app(self.app)
        self.app.add_url_rule('/normalizaciones', view_func=unwrap(api_normalizaciones_proyectados), methods=['POST'])
        self.app.add_url_rule('/normalizaciones/<int:normalizacion_id>', view_func=unwrap(api_eliminar_normalizacion_proyectados), methods=['DELETE'])
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([Campania(id=i, cliente='Cliente', nombre=f'Campaña {i}') for i in (1, 2, 3)])
        db.session.add(NormalizacionNombreProyectado(campania_id=1, cliente_proyectado='Anterior', servicio_proyectado='Anterior'))
        db.session.commit()
        self.client = self.app.test_client()
        self.summary = patch('app.routes.construir_resumen_proyeccion_data', return_value={})
        self.consolidate = patch('app.routes.consolidar_resumen_proyeccion', return_value={
            'filas': [{'tipo': 'detalle', 'cliente': 'Cliente', 'campania': 'Servicio', 'total': 10}]})
        self.summary.start()
        self.consolidate.start()

    def tearDown(self):
        self.summary.stop()
        self.consolidate.stop()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def post(self, **kwargs):
        return self.client.post('/normalizaciones', json={
            'cliente_proyectado': 'Cliente', 'servicio_proyectado': 'Servicio', **kwargs})

    def test_lote_mueve_y_crea_sin_duplicar(self):
        response = self.post(campania_ids=[1, 2, 2])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['normalizaciones']), 2)
        db.session.expire_all()
        self.assertEqual(NormalizacionNombreProyectado.query.count(), 2)
        self.assertEqual(HistorialCambio.query.count(), 2)
        moved = HistorialCambio.query.filter_by(accion='edicion').one().to_dict()
        self.assertEqual(moved['antes']['servicio_proyectado'], 'Anterior')
        self.assertEqual(moved['despues']['servicio_proyectado'], 'Servicio')
        self.assertTrue(all(row.servicio_proyectado == 'Servicio' for row in NormalizacionNombreProyectado.query.all()))
        self.assertEqual(self.post(campania_ids=[1, 2]).status_code, 200)
        self.assertEqual(NormalizacionNombreProyectado.query.count(), 2)
        self.assertEqual(HistorialCambio.query.count(), 2)
        relation = NormalizacionNombreProyectado.query.filter_by(campania_id=2).one()
        self.assertEqual(self.client.delete(f'/normalizaciones/{relation.id}').status_code, 200)
        removed = HistorialCambio.query.filter_by(accion='eliminacion').one().to_dict()
        self.assertEqual(removed['antes']['campania_id'], 2)
        self.assertIsNone(removed['despues'])

    def test_id_inexistente_no_guarda_parcialmente(self):
        self.assertEqual(self.post(campania_ids=[1, 2, 999]).status_code, 404)
        self.assertEqual(NormalizacionNombreProyectado.query.count(), 1)
        self.assertEqual(NormalizacionNombreProyectado.query.first().servicio_proyectado, 'Anterior')

    def test_seleccion_invalida(self):
        for value in ([], None, '1', [True], [1.5], ['incorrecto']):
            with self.subTest(value=value):
                self.assertEqual(self.post(campania_ids=value).status_code, 400)
        self.assertEqual(NormalizacionNombreProyectado.query.count(), 1)

    def test_compatible_con_guardado_individual(self):
        response = self.post(campania_id=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['normalizacion']['campania_id'], 3)


if __name__ == '__main__':
    unittest.main()
