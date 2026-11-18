"""Verifica las prioridades de jefatura informadas para Personal."""
from pathlib import Path
import sys
import unittest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db
from app.models import AsignacionComercial, Campania, normalizar_jefe_site
from app.routes import jefe_personal_por_servicio, resolver_personal_importacion_directa, segmento_personal_por_servicio


class JefaturasPersonalTest(unittest.TestCase):
    def test_jefatura_por_grupo_y_servicio(self):
        casos = [
            (('Personal SMB', 'Ventas Digital'), 'Canalini, Walter'),
            (('Personal Soporte', 'Retención'), 'Canalini, Walter'),
            (('Personal CX', 'Retención Convergente'), 'Del Soto, Alejandro'),
            (('Personal CX', 'Ventas'), 'Chanampa, Pablo'),
            (('Personal CX', 'GCR'), 'Chanampa, Pablo'),
            (('Personal CX', 'Customer'), 'Antelo, Micaela'),
        ]
        for valores, esperado in casos:
            with self.subTest(valores=valores):
                self.assertEqual(normalizar_jefe_site(jefe_personal_por_servicio(*valores)), esperado)

    def test_gcr_se_clasifica_como_ventas(self):
        self.assertEqual(segmento_personal_por_servicio('GCR'), 'Ventas')


class GrupoPersonalImportacionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        campania = Campania(cliente='Personal', nombre='Capacitaciones')
        db.session.add(campania)
        for grupo, jefe in [('Personal CX', 'Antelo, Micaela'), ('Personal Soporte', 'Canalini, Walter')]:
            db.session.add(AsignacionComercial(campania_catalogo=campania, cliente='Personal',
                gerente='Caamaño, Lucas', jefe_site=jefe, campania='Capacitaciones',
                subcampania='Capacitaciones', tipo_negocio=grupo, activa=True))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_desambiguar_grupo(self):
        item = {'cliente': 'Personal', 'subcampania': 'Capacitaciones', 'tipo_negocio': 'Personal Soporte'}
        asignacion, error = resolver_personal_importacion_directa(item)
        self.assertIsNone(error)
        self.assertEqual(asignacion.jefe_site, 'Canalini, Walter')
        self.assertEqual(item['tipo_negocio'], 'Personal Soporte')

    def test_rechaza_servicio_ambiguo_sin_grupo(self):
        asignacion, error = resolver_personal_importacion_directa(
            {'cliente': 'Personal', 'subcampania': 'Capacitaciones'})
        self.assertIsNone(asignacion)
        self.assertIn('varios grupos', error)


if __name__ == '__main__':
    unittest.main()
