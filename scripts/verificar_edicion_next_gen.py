"""Prueba la edición agrupada de Next Gen sin modificar la base real."""
from inspect import unwrap
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask

from app import db
from app.models import HistorialCambio, NextGenDolar, NextGenProducto
from app.routes import api_edicion_masiva_next_gen


class EdicionNextGenTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', DEFAULT_YEAR=2026, TESTING=True)
        db.init_app(self.app)
        self.app.add_url_rule(
            '/api/next-gen/edicion-masiva',
            view_func=unwrap(api_edicion_masiva_next_gen), methods=['POST'],
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add_all([
            NextGenDolar(year=2026, mes='2026-01', valor=1000),
            NextGenProducto(
                site='Site', cliente='Cliente', campania='Campaña', producto='Producto',
                year=2026, mes='2026-01', cantidad_usd=10,
            ),
        ])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_guarda_dolar_y_producto_en_una_operacion(self):
        response = self.client.post('/api/next-gen/edicion-masiva', json={
            'year': 2026,
            'cambios': [
                {'tipo': 'dolar', 'mes': '2026-01', 'valor': 1500},
                {
                    'tipo': 'producto', 'site': 'Site', 'cliente': 'Cliente',
                    'campania': 'Campaña', 'producto': 'Producto',
                    'mes': '2026-01', 'cantidad_usd': 12,
                },
            ],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NextGenDolar.query.one().valor, 1500)
        self.assertEqual(NextGenProducto.query.one().cantidad_usd, 12)
        self.assertEqual(response.json['next_gen']['total_pesos']['total'], 18000)
        self.assertEqual(HistorialCambio.query.count(), 1)
        self.assertIn('2 celda(s)', HistorialCambio.query.one().resumen)

    def test_error_no_guarda_parcialmente(self):
        response = self.client.post('/api/next-gen/edicion-masiva', json={
            'year': 2026,
            'cambios': [
                {'tipo': 'dolar', 'mes': '2026-01', 'valor': 2000},
                {'tipo': 'producto', 'mes': '2027-01', 'cantidad_usd': 99},
            ],
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(NextGenDolar.query.one().valor, 1000)
        self.assertEqual(NextGenProducto.query.one().cantidad_usd, 10)
        self.assertEqual(HistorialCambio.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
