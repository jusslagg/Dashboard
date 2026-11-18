"""Selección y presentación de la apertura mensual de desvíos."""
from collections import defaultdict
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import _clave_nombre

MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
CONCEPTOS = (
    ('cumplimiento_horas', '% Cumplimiento horas', 'porcentaje'),
    ('valor_hora', '% Valor hora', 'porcentaje'),
    ('cumplimiento_facturacion', '% Cumplimiento facturación', 'porcentaje'),
    ('horas', 'Horas', 'importe'),
    ('variable', 'Variable', 'importe'),
    ('bonos_penalizaciones', 'Penalizaciones / Bonos', 'importe'),
    ('porcentaje_desvio', '% Desvío facturación', 'porcentaje'),
    ('total', 'TOTAL', 'importe'),
)
ORDEN_ORIGEN = ('Personal', 'SANTANDER', 'BBVA', 'QUALIA', 'ASSURANT', 'GIRE', 'CACHAMAI',
                'BICE', 'FARMAPAY', 'YAMAHA', 'JOHNSON & JOHNSON', 'BANCO COMAFI', 'BIBANK',
                'OPENPAY', 'BANCO PIANO', 'METROGAS', 'SPAZIOS', 'SUPERVIELLE SEGUROS',
                'SUPERVIELLE', 'LEIVA JOYAS', 'NATURGY', 'BSF CARREFOUR', 'MIRGOR', 'OMINT',
                'RIVER PLATE', 'UNICEF', 'GALICIA', 'BNA')
ORDEN = {_clave_nombre(cliente): i for i, cliente in enumerate(ORDEN_ORIGEN)}


@lru_cache(maxsize=1)
def datos_cache_assurant():
    return json.loads((Path(__file__).parent / 'data' / 'assurant_agosto_cache.json').read_text(encoding='utf-8'))


def incorporar_recuperacion_parcial(datos, registros_existentes):
    """Expone la caché identificada sin reemplazar los registros vigentes."""
    recuperado = datos_cache_assurant()
    clave = (_clave_nombre(recuperado['cliente']), recuperado['mes'])
    existentes = {(_clave_nombre(cliente), mes) for cliente, mes in registros_existentes}
    datos['recuperaciones'] = []
    if datos['year'] != 2026 or clave in existentes:
        return datos
    parcial = {'cliente': recuperado['cliente'], 'campania': None, 'mes': recuperado['mes'],
        'cumplimiento_horas': recuperado['horas_facturadas'] / recuperado['horas_objetivo'],
        'valor_hora': None, 'cumplimiento_facturacion': None, 'horas': None, 'variable': None,
        'bonos_penalizaciones': None, 'porcentaje_desvio': None, 'total': None,
        'fuente_parcial': recuperado}
    datos['filas'].append(parcial)
    datos['campanias'].append({**parcial, 'campania': recuperado['campania']})
    datos['recuperaciones'].append(recuperado)
    return datos


def filtrar_apertura(datos, cliente='', campania='', mes=''):
    filas = datos['campanias'] if campania else datos['filas']
    agrupados = defaultdict(dict)
    for fila in filas:
        if cliente and _clave_nombre(fila['cliente']) != _clave_nombre(cliente):
            continue
        if campania and _clave_nombre(fila['campania']) != _clave_nombre(campania):
            continue
        agrupados[fila['cliente']][fila['mes'][-2:]] = fila
    if mes and not cliente:
        agrupados = {nombre: valores for nombre, valores in agrupados.items() if mes in valores}
    cuentas = sorted(agrupados, key=lambda nombre: (
        _clave_nombre(nombre) == 'totalgeneral', ORDEN.get(_clave_nombre(nombre), len(ORDEN)),
        _clave_nombre(nombre)))
    return [(nombre, agrupados[nombre]) for nombre in cuentas]


def exportar_apertura(datos, cliente='', campania='', mes=''):
    cuentas = filtrar_apertura(datos, cliente, campania, mes)
    meses = [int(mes)] if mes else list(range(1, 13))
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Apertura desvíos'
    ultima_columna = 2 + len(meses)
    ultima_letra = get_column_letter(ultima_columna)
    hoja.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ultima_columna)
    hoja['A1'] = 'APERTURA DE DESVÍOS POR CLIENTE'
    hoja['A1'].font = Font(name='Calibri', size=16, bold=True, color='FFFFFF')
    hoja['A1'].fill = PatternFill('solid', fgColor='183153')
    hoja['A1'].alignment = Alignment(vertical='center')
    hoja.row_dimensions[1].height = 34
    hoja.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ultima_columna)
    hoja['A2'] = (f"{datos['year']}  |  Cliente: {cliente or 'Todos'}  |  "
                  f"Campaña: {campania or 'Todas'}  |  Mes: {MESES[int(mes)-1] if mes else 'Todos'}")
    hoja['A2'].font = Font(name='Calibri', size=10, color='52677F')
    hoja.row_dimensions[2].height = 25
    for columna, titulo in enumerate(['Cuenta', 'Concepto'] + [MESES[m-1] for m in meses], 1):
        celda = hoja.cell(4, columna, titulo)
        celda.fill = PatternFill('solid', fgColor='284B70')
        celda.font = Font(name='Calibri', bold=True, color='FFFFFF')
        celda.alignment = Alignment(vertical='center', horizontal='left' if columna <= 2 else 'right')
    hoja.row_dimensions[4].height = 25
    fila_excel = 5
    for indice, (nombre, valores) in enumerate(cuentas):
        for posicion, (campo, etiqueta, tipo) in enumerate(CONCEPTOS):
            fila = fila_excel + posicion
            hoja.cell(fila, 1, nombre if posicion == 0 else '')
            hoja.cell(fila, 2, etiqueta)
            for columna, numero_mes in enumerate(meses, 3):
                valor = (valores.get(f'{numero_mes:02d}') or {}).get(campo)
                if valor is not None:
                    celda = hoja.cell(fila, columna, valor)
                    celda.number_format = ('0.0%;[Red](0.0%);0.0%' if tipo == 'porcentaje'
                                           else '#,##0.00;[Red](#,##0.00);0.00')
                    if (valores.get(f'{numero_mes:02d}') or {}).get('fuente_parcial'):
                        celda.comment = Comment('Dato recuperado de una tabla dinámica guardada; no figura en la base actual. El valor hora objetivo no está disponible.', 'Fuente del dato')
            for columna in range(1, ultima_columna + 1):
                celda = hoja.cell(fila, columna)
                if isinstance(celda.value, str):
                    celda.data_type = 's'
                celda.font = Font(name='Calibri', size=10, bold=posicion == 7 or (posicion == 0 and columna == 1),
                                  color='183153' if posicion == 7 else '253B53')
                celda.fill = PatternFill('solid', fgColor='E3ECF6' if posicion == 7 else
                                        ('F5F8FC' if indice % 2 else 'FFFFFF'))
                celda.alignment = Alignment(vertical='center', horizontal='right' if columna >= 3 else 'left')
                if posicion == 7:
                    celda.border = Border(top=Side(style='thin', color='AABED2'))
            hoja.row_dimensions[fila].height = 19
        fila_excel += len(CONCEPTOS)
    if not cuentas:
        hoja.cell(5, 1, 'Sin datos para la selección.')
    parcial_incluido = any(
        fila.get('fuente_parcial') for _, valores in cuentas for numero, fila in valores.items()
        if not mes or numero == mes)
    total_incluido = any(_clave_nombre(nombre) == 'totalgeneral' for nombre, _ in cuentas)
    if datos.get('recuperaciones') and (parcial_incluido or (total_incluido and mes in ('', '08'))):
        fila_nota = fila_excel + 1
        hoja.merge_cells(start_row=fila_nota, start_column=1, end_row=fila_nota, end_column=ultima_columna)
        hoja.cell(fila_nota, 1, 'Assurant agosto: porcentaje de horas recuperado de una tabla dinámica guardada; el registro no figura en la base actual y no está incluido en el total general. Falta el valor hora objetivo para calcular los desvíos.')
        hoja.cell(fila_nota, 1).font = Font(name='Calibri', size=10, italic=True, color='76540B')
        hoja.cell(fila_nota, 1).alignment = Alignment(wrap_text=True, vertical='center')
        hoja.cell(fila_nota, 1).fill = PatternFill('solid', fgColor='FFF7DF')
        hoja.row_dimensions[fila_nota].height = 45
        fila_excel = fila_nota + 1
    hoja.column_dimensions['A'].width = 24
    hoja.column_dimensions['B'].width = 31
    for columna in range(3, ultima_columna + 1):
        hoja.column_dimensions[get_column_letter(columna)].width = 20
    hoja.freeze_panes = 'C5'
    hoja.sheet_view.showGridLines = False
    hoja.print_title_rows = '1:4'
    hoja.print_options.horizontalCentered = True
    hoja.page_setup.orientation = 'landscape'
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.print_area = f'A1:{ultima_letra}{max(5, fila_excel - 1)}'
    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
