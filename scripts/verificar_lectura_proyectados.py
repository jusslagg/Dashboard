"""Comprueba la lectura de columnas mensuales de los libros de proyección."""
from datetime import datetime
from pathlib import Path
import sys
import unittest

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.sincronizar_proyectados_excel import datos_tabla_mensual
from scripts.verificar_alineacion_proyectados import formula_bi_bank_ausente


class ColumnasProyectadosTest(unittest.TestCase):
    def hoja(self, encabezado, fila):
        hoja = Workbook().active
        for _ in range(3):
            hoja.append([])
        hoja.append(encabezado)
        hoja.append(fila)
        return hoja

    def test_precios_con_columnas_desplazadas(self):
        fecha = datetime(2026, 1, 1)
        hoja = self.hoja(
            ['Comentarios', None, 'CUENTA (CLIENTE)', None, 'Site', 'CLAVE OPERATIVA', 'Tipo VH', 'ultimo precio', fecha],
            [None, '#REF!', 'Cuenta prueba', None, 'Site prueba', 'Servicio prueba', 'Horas', 0, 25],
        )
        cuenta, site, campania, fila, columnas = next(datos_tabla_mensual(hoja))
        self.assertEqual((cuenta, site, campania), ('Cuenta prueba', 'Site prueba', 'Servicio prueba'))
        self.assertEqual([(indice, mes, fila[indice]) for indice, mes in columnas], [(8, '2026-01', 25)])

    def test_formato_usado_por_variables_y_tarifacion(self):
        fecha = datetime(2026, 1, 1)
        hoja = self.hoja(
            [None, None, 'CUENTA (CLIENTE)', 'Site', 'CLAVE OPERATIVA', None, 'CAMPAÑA', fecha],
            [None, None, 'Cuenta prueba', 'Site prueba', 'Servicio prueba', None, 'Servicio prueba', 0.05],
        )
        cuenta, site, campania, fila, columnas = next(datos_tabla_mensual(hoja))
        self.assertEqual((cuenta, site, campania), ('Cuenta prueba', 'Site prueba', 'Servicio prueba'))
        self.assertEqual([(indice, mes, fila[indice]) for indice, mes in columnas], [(7, '2026-01', 0.05)])

    def test_excepcion_historica_no_oculta_diferencias_en_ejercicios_nuevos(self):
        libro = Workbook()
        libro.active.title = 'Next Gen'
        self.assertTrue(formula_bi_bank_ausente(libro, 'Next Gen', 'bi bank', '2026-03', 100, 0))
        self.assertFalse(formula_bi_bank_ausente(libro, 'Next Gen', 'bi bank', '2027-03', 100, 0))


if __name__ == '__main__':
    unittest.main()
