"""Pruebas de aperturas, agrupación PLP y tipos de celda de la exportación."""
from pathlib import Path
import sys
import unittest
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook, load_workbook
from app.proyecciones_export import projection_rows, table, PERCENT
from app.resumen_layout import construir_apoyo_resumen, construir_formato_resumen
from app.unificado import construir_unificado


class ExportacionProyectadosTest(unittest.TestCase):
    def item(self, **changes):
        return dict(cliente='Personal', campania='Servicio', year=2026, mes='2026-01', mes_label='Ene-26',
                    dotacion_requerida=10, carga_semanal='L a V', carga_horaria=6, dias_objetivo=20,
                    horas_requeridas=1200, horas_proyectadas=1080, porcentaje_cumplimiento=90,
                    tiene_nocturnidad=True, porcentaje_nocturnidad=20, **changes)

    def test_todas_separa_nocturnidad_y_excluye_plp(self):
        rows = list(projection_rows([self.item(), self.item(tipo_plp='Personal')]))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row[4] for row in rows], [8, 2])
        self.assertEqual(sum(row[9] for row in rows), 1080)
        self.assertEqual(rows[1][1], 'Servicio nocturnidad')
        self.assertEqual(rows[0][10], .9)

    def test_plp_agrupa_servicios_y_conserva_horas(self):
        rows = list(projection_rows([self.item(tipo_plp='Personal'), self.item(tipo_plp='Personal')], True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row[8] for row in rows), 2400)
        self.assertEqual(sum(row[9] for row in rows), 2160)
        self.assertEqual(rows[0][10], .9)

    def test_celdas_numericas_y_texto_literal(self):
        book = Workbook(); book.remove(book.active)
        table(book, 'Prueba', ['Nombre', 'Porcentaje'], [['=1+1', .2]], {2: PERCENT})
        output = BytesIO(); book.save(output); output.seek(0)
        sheet = load_workbook(output).active
        self.assertEqual(sheet['A2'].data_type, 's')
        self.assertEqual(sheet['B2'].value, .2)
        self.assertEqual(sheet['B2'].number_format, PERCENT)

    def test_formato_conserva_celdas_y_agrega_campanias_al_final(self):
        meses = [{'value': f'2027-{i:02d}'} for i in range(1, 13)]
        def fila(nombre, valor):
            return {'tipo': 'detalle', 'site': 'Gerencia Multicampaña', 'cliente': nombre,
                    'campania': nombre, 'concepto': 'Horas',
                    'origenes': [{'cliente': nombre, 'campania': nombre}],
                    'meses': {m['value']: valor if m['value'].endswith('-01') else 0 for m in meses}}
        resultado = construir_formato_resumen({'meses': meses, 'filas': [fila('ASSURANT', 100), fila('CUENTA NUEVA PRUEBA', 50)]})
        por_fila = {item['fila_excel']: item for item in resultado}
        self.assertEqual(por_fila[27]['campania'], 'ASSURANT')
        self.assertEqual(por_fila[27]['meses']['2027-01'], 100)
        self.assertEqual(por_fila[31]['meses']['2027-01'], 100)
        self.assertEqual(por_fila[122]['campania'], 'SANTANDER LEADS')
        self.assertEqual(por_fila[257]['campania'], 'MORA TARDÍA')
        self.assertEqual(por_fila[264]['campania'], 'CUENTA NUEVA PRUEBA')
        self.assertEqual(por_fila[268]['meses']['2027-01'], 50)
        self.assertEqual(por_fila[4]['meses']['2027-01'], 150)

    def test_nuevo_cliente_con_operativa_existente_no_se_mezcla(self):
        meses = [{'value': f'2027-{i:02d}'} for i in range(1, 13)]
        def fila(cliente, valor):
            return {'tipo': 'detalle', 'site': 'Gerencia Multicampaña', 'cliente': cliente,
                    'campania': 'ASSURANT', 'concepto': 'Horas',
                    'origenes': [{'cliente': cliente, 'campania': 'ASSURANT'}],
                    'meses': {m['value']: valor if m['value'].endswith('-01') else 0 for m in meses}}
        resultado = construir_formato_resumen({'meses': meses, 'filas': [fila('ASSURANT', 100), fila('OTRO CLIENTE', 50)]})
        por_fila = {item['fila_excel']: item for item in resultado}
        self.assertEqual(por_fila[27]['meses']['2027-01'], 100)
        self.assertEqual(por_fila[264]['cliente'], 'OTRO CLIENTE')
        self.assertEqual(por_fila[268]['meses']['2027-01'], 50)
        self.assertEqual(por_fila[4]['meses']['2027-01'], 150)

    def test_apoyo_cce_excluye_misma_operativa_de_cliente_nuevo(self):
        meses = [{'value': '2027-01'}]
        def fila(cliente, campania, importe):
            return {'tipo': 'detalle', 'site': 'Gerencia', 'cliente': cliente,
                    'concepto': 'Horas', 'origenes': [{'cliente': cliente, 'campania': campania}],
                    'meses': {'2027-01': importe}}
        datos = {'meses': meses, 'filas': [fila('SANTANDER', 'SANTANDER CHAT', 100),
                                        fila('CLIENTE NUEVO', 'SANTANDER CHAT', 50),
                                        fila('CLIENTE NUEVO', 'SANTANDER CHAT nocturnidad', 20)]}
        apoyo = construir_apoyo_resumen(datos)
        resultado = {item['fila_excel']: item for item in construir_formato_resumen(datos)}
        self.assertEqual(apoyo[11], 100)
        self.assertEqual(resultado[264]['cliente'], 'CLIENTE NUEVO')
        self.assertEqual(resultado[268]['meses']['2027-01'], 70)

    def test_nuevo_servicio_va_debajo_del_anterior_aunque_ordene_antes_por_nombre(self):
        meses = [{'value': '2027-01'}]
        def fila(nombre, fecha, importe):
            return {'tipo': 'detalle', 'site': 'Gerencia', 'cliente': nombre,
                    'concepto': 'Horas', 'orden_alta': fecha,
                    'origenes': [{'cliente': nombre, 'campania': nombre}],
                    'meses': {'2027-01': importe}}
        anterior = fila('Z SERVICIO', '2027-01-01T09:00:00', 100)
        nuevo = fila('A SERVICIO', '2027-02-01T09:00:00', 50)
        resultado = {item['fila_excel']: item for item in
                     construir_formato_resumen({'meses': meses, 'filas': [nuevo, anterior]})}
        self.assertEqual(resultado[264]['campania'], 'Z SERVICIO')
        self.assertEqual(resultado[269]['campania'], 'A SERVICIO')
        self.assertEqual([resultado[i]['concepto'] for i in range(269, 274)],
                         ['Horas', 'Variable Productividad', 'Next Gen', 'Tarifacion + otros', 'Total'])
        self.assertEqual(resultado[273]['meses']['2027-01'], 50)

    def test_unificado_conserva_aperturas_y_agrega_servicios_por_orden_de_alta(self):
        meses = [{'value': '2027-01'}]
        def fila(cliente, nombre, importe, fecha):
            return {'tipo': 'detalle', 'site': 'Gerencia', 'cliente': cliente, 'concepto': 'Horas',
                    'orden_alta': fecha, 'origenes': [{'cliente': cliente, 'campania': nombre}],
                    'meses': {'2027-01': importe}}
        datos = {'year': 2027, 'meses': meses, 'filas': [
            fila('Personal', 'Personal nocturnidad', 10, '2027-01-01'),
            fila('NATURGY', 'Naturgy NOA nocturnidad', 20, '2027-01-01'),
            fila('A NUEVA', 'A NUEVA', 30, '2027-03-01'),
            fila('Z NUEVA', 'Z NUEVA', 40, '2027-02-01')]}
        filas = construir_unificado(datos)['filas']
        por_clave = {fila['clave_operativa']: fila for fila in filas}
        self.assertEqual(por_clave['Personal Nocturnos']['meses']['2027-01'], 10)
        self.assertEqual(por_clave['Personal']['meses']['2027-01'], 0)
        self.assertEqual(por_clave['NATURGY NOA']['meses']['2027-01'], 20)
        self.assertEqual([fila['clave_operativa'] for fila in filas[-2:]], ['Z NUEVA', 'A NUEVA'])

    def test_unificado_separa_cliente_nuevo_con_nombre_operativo_existente(self):
        meses = [{'value': '2027-01'}]
        def fila(cliente, importe):
            return {'tipo': 'detalle', 'site': 'Gerencia', 'cliente': cliente, 'concepto': 'Horas',
                    'origenes': [{'cliente': cliente, 'campania': 'ASSURANT'}],
                    'meses': {'2027-01': importe}}
        filas = construir_unificado({'year': 2027, 'meses': meses,
                                     'filas': [fila('ASSURANT', 100), fila('CLIENTE NUEVO', 50)]})['filas']
        self.assertEqual(filas[0]['meses']['2027-01'], 100)
        self.assertEqual(filas[-1]['cliente'], 'CLIENTE NUEVO')
        self.assertEqual(filas[-1]['meses']['2027-01'], 50)


if __name__ == '__main__':
    unittest.main()
