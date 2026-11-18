"""Verifica filtros, aperturas por campaña y descarga individual."""
from io import BytesIO
from pathlib import Path
import sys
import unittest

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Facturacion2026, Usuario


class AperturaFuncionalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        cls.context = cls.app.app_context()
        cls.context.push()
        cls.client = cls.app.test_client()
        usuario = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
        assert usuario
        with cls.client.session_transaction() as sesion:
            sesion['usuario_id'] = usuario.id
        cls.data = cls.client.get('/api/apertura-desvios-clientes?year=2026').get_json()

    @classmethod
    def tearDownClass(cls):
        cls.context.pop()

    def test_agosto_assurant_muestra_registro_confirmado(self):
        fila = next(f for f in self.data['filas'] if f['cliente'].lower() == 'assurant' and f['mes'] == '2026-08')
        self.assertAlmostEqual(fila['cumplimiento_horas'], 1899 / 1800)
        self.assertAlmostEqual(fila['horas'], 1880373.33, places=2)
        self.assertAlmostEqual(fila['variable'], -114732, places=2)
        self.assertAlmostEqual(fila['total'], 1765641.33, places=2)
        self.assertFalse(fila.get('fuente_parcial'))
        response = self.client.get('/api/apertura-desvios-clientes/exportar',
            query_string={'year': 2026, 'cliente': 'Assurant', 'mes': '08'})
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.data), data_only=True).active
        self.assertEqual(sheet['C4'].value, 'Agosto')
        self.assertEqual(sheet['A5'].value, 'Assurant')
        self.assertAlmostEqual(sheet['C5'].value, 1899 / 1800)
        self.assertIsNone(sheet['C5'].comment)
        self.assertAlmostEqual(sheet['C8'].value, 1880373.33, places=2)
        self.assertAlmostEqual(sheet['C9'].value, -114732, places=2)
        self.assertAlmostEqual(sheet['C12'].value, 1765641.33, places=2)
        self.assertEqual(sheet.max_column, 3)

    def test_cache_parcial_solo_si_no_hay_registro_real(self):
        from app.apertura_desvios import incorporar_recuperacion_parcial
        datos = {'year': 2026, 'filas': [], 'campanias': []}
        incorporar_recuperacion_parcial(datos, [])
        fila = datos['filas'][0]
        self.assertAlmostEqual(fila['cumplimiento_horas'], 1899.03 / 1800)
        self.assertTrue(all(fila[campo] is None for campo in ('horas', 'variable', 'total', 'valor_hora')))

    def test_registro_real_tiene_prioridad_sobre_cache(self):
        from app.apertura_desvios import incorporar_recuperacion_parcial
        datos = {'year': 2026, 'filas': [], 'campanias': []}
        incorporar_recuperacion_parcial(datos, [('ASSURANT', '2026-08')])
        self.assertEqual(datos['filas'], [])
        self.assertEqual(datos['recuperaciones'], [])

    def test_campania_tiene_sus_propios_importes_y_descarga(self):
        fila = next(f for f in self.data['campanias'] if f['cliente'].lower() == 'santander'
                    and f['campania'].lower() == 'santander chat' and f['mes'] == '2026-09')
        registros = [r for r in Facturacion2026.query.filter_by(mes='2026-09').all()
                     if r.cliente.lower() == 'santander' and (r.campania or '').lower() == 'santander chat'
                     and (r.mes_apertura_origen or r.mes) == '2026-09']
        esperado = sum(float(r.facturado_horas_control or 0) - float(r.objetivo_facturacion_horas or 0)
                       for r in registros)
        self.assertAlmostEqual(fila['horas'], esperado, places=4)
        response = self.client.get('/api/apertura-desvios-clientes/exportar', query_string={
            'year': 2026, 'cliente': fila['cliente'], 'campania': fila['campania'], 'mes': '09'})
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.data), data_only=True).active
        self.assertEqual(sheet['C4'].value, 'Septiembre')
        self.assertAlmostEqual(sheet['C8'].value, esperado, places=4)
        self.assertEqual(sheet.max_row, 12)

    def test_parametros_y_formato_de_reporte(self):
        self.assertEqual(self.client.get('/api/apertura-desvios-clientes/exportar?year=2026&mes=13').status_code, 400)
        response = self.client.get('/api/apertura-desvios-clientes/exportar?year=2026')
        sheet = load_workbook(BytesIO(response.data), data_only=True).active
        self.assertEqual([sheet.cell(4, n).value for n in range(1, 5)], ['Cuenta', 'Concepto', 'Enero', 'Febrero'])
        self.assertEqual(sheet['A5'].value, 'Personal')
        self.assertEqual(sheet['A13'].value.upper(), 'SANTANDER')
        self.assertEqual(sheet.freeze_panes, 'C5')
        self.assertEqual(sheet['C5'].number_format, '0.0%;[Red](0.0%);0.0%')


if __name__ == '__main__':
    unittest.main()
