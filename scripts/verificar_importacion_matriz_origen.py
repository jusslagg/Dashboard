"""Comprueba que importar una matriz no recalcula las horas del libro."""
from datetime import datetime
import os
from pathlib import Path
import sys
import unittest

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite://'
from app import create_app, db
from app.models import ProyeccionMatriz
from scripts.sincronizar_proyectados_excel import sincronizar_matriz


class ImportacionMatrizOrigenTest(unittest.TestCase):
    def test_preserva_horas_calculadas_por_el_archivo(self):
        app = create_app()
        libro = Workbook()
        hoja = libro.active
        hoja.title = 'Matriz'
        hoja.append([])
        hoja.append([])
        fila = [None] * 16
        fila[2:12] = ['Cuenta de prueba', 'Campaña de prueba', 2026,
                      datetime(2026, 1, 1), 'L a V', 20, 6, 4, 999.125, 975.5]
        hoja.append(fila)
        with app.test_request_context('/'):
            self.assertEqual(sincronizar_matriz(libro), 1)
            registro = ProyeccionMatriz.query.filter_by(cliente='Cuenta de prueba').one()
            self.assertAlmostEqual(registro.horas_requeridas, 999.125)
            self.assertAlmostEqual(registro.horas_proyectadas, 975.5, places=2)
            self.assertEqual(registro.jornadas[0].dias_objetivo, 20)
            db.session.rollback()


if __name__ == '__main__':
    unittest.main()
