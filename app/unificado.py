"""Unificado por clave operativa, calculado con las proyecciones vigentes."""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

from app.models import _clave_nombre


@lru_cache(maxsize=1)
def formato_unificado():
    return json.loads((Path(__file__).parent / 'data' / 'formato_unificado.json').read_text(encoding='utf-8'))


def construir_unificado(data):
    from app.routes import normalizar_nombre_variable
    from app.resumen_layout import formato

    def exacta(valor):
        return ' '.join(str(valor or '').strip().casefold().split())

    definiciones = formato_unificado()
    pares_conocidos = {(_clave_nombre(cliente), _clave_nombre(normalizar_nombre_variable(operativa)))
                       for cliente, operativa in formato().get('pares_conocidos', [])}
    meses = [item['value'] for item in data['meses']]
    por_nombre = {exacta(fila['clave_operativa']): fila for fila in definiciones}
    alternativas = defaultdict(list)
    for nombre, fila in por_nombre.items():
        alternativas[_clave_nombre(normalizar_nombre_variable(nombre))].append(fila)

    def encontrar(nombre):
        nombre = str(nombre or '').strip()
        fila = por_nombre.get(exacta(nombre))
        if fila:
            return fila
        candidatos = alternativas[_clave_nombre(normalizar_nombre_variable(nombre))]
        if len(candidatos) == 1:
            return candidatos[0]
        # La nocturnidad desglosada de una misma clave forma parte de esa clave.
        if nombre.casefold().endswith(' nocturnidad'):
            base = nombre[:-len(' nocturnidad')]
            fila = por_nombre.get(exacta(base))
            if fila:
                return fila
        if nombre.casefold().endswith(' nocturnidad'):
            candidatos = alternativas[_clave_nombre(normalizar_nombre_variable(nombre[:-len(' nocturnidad')]))]
            if len(candidatos) == 1:
                return candidatos[0]
        return None

    importes = defaultdict(lambda: {mes: 0.0 for mes in meses})
    adicionales = {}
    for fila in data.get('filas', []):
        if fila.get('tipo') != 'detalle':
            continue
        for origen in fila.get('origenes', []):
            nombre = str(origen.get('campania') or '').strip()
            if not nombre:
                continue
            definicion = encontrar(nombre)
            cliente_clave = _clave_nombre(origen.get('cliente'))
            operativa_clave = _clave_nombre(normalizar_nombre_variable(nombre))
            par_conocido = (cliente_clave, operativa_clave) in pares_conocidos
            if nombre.casefold().endswith(' nocturnidad'):
                base_clave = _clave_nombre(normalizar_nombre_variable(nombre[:-len(' nocturnidad')]))
                par_conocido = par_conocido or (cliente_clave, base_clave) in pares_conocidos
            if pares_conocidos and not par_conocido:
                definicion = None
            if definicion:
                valores = importes[definicion['fila_excel']]
            else:
                if nombre.casefold().endswith(' nocturnidad'):
                    nombre = nombre[:-len(' nocturnidad')]
                identidad = (exacta(origen.get('cliente')), exacta(nombre))
                grupo = adicionales.setdefault(identidad, {
                    'cliente_proyectado': origen.get('cliente') or fila.get('cliente') or '',
                    'clave_agrupacion': '', 'cliente': origen.get('cliente') or fila.get('cliente') or '',
                    'site': fila.get('site') or '', 'clave_operativa': nombre,
                    'segmento': '', 'campania': nombre, 'orden_alta': fila.get('orden_alta'),
                    'meses': {mes: 0.0 for mes in meses}})
                if fila.get('orden_alta'):
                    grupo['orden_alta'] = min(grupo.get('orden_alta') or fila['orden_alta'], fila['orden_alta'])
                valores = grupo['meses']
            for mes in meses:
                valores[mes] += float(fila.get('meses', {}).get(mes, 0) or 0)

    salida = []
    for definicion in definiciones:
        fila = dict(definicion)
        fila['meses'] = {mes: round(importes[fila['fila_excel']][mes], 10) for mes in meses}
        fila['total'] = round(sum(fila['meses'].values()), 10)
        salida.append(fila)
    numero = max((fila['fila_excel'] for fila in salida), default=4) + 1
    for fila in sorted(adicionales.values(), key=lambda item: item['orden_alta'] or '9999'):
        fila['fila_excel'] = numero
        fila['total'] = round(sum(fila['meses'].values()), 10)
        salida.append(fila)
        numero += 1
    totales = {mes: round(sum(fila['meses'][mes] for fila in salida), 10) for mes in meses}
    return {'success': True, 'year': data['year'], 'meses': data['meses'], 'filas': salida,
            'totales': totales, 'total': round(sum(totales.values()), 10)}


def agregar_hoja_unificado(libro, data):
    """Construye la hoja con las mismas columnas principales del libro fuente."""
    from datetime import datetime
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    hoja = libro.create_sheet('Unificado')
    campos = ('cliente_proyectado', 'clave_agrupacion', 'cliente', 'site',
              'clave_operativa', 'segmento', 'campania')
    titulos = ('Cliente Proyectado', None, 'CUENTA (CLIENTE)', 'Site',
               'CLAVE OPERATIVA', 'SEGMENTO', 'CAMPAÑA')
    for columna, titulo in enumerate(titulos, 1):
        if titulo:
            hoja.cell(4, columna, titulo)
    for columna, mes in enumerate(data['meses'], 8):
        numero_mes = int(mes['value'][-2:])
        hoja.cell(4, columna, datetime(data['year'], numero_mes, 1)).number_format = 'mmm-yy'
        for fila in (2, 3):
            hoja.cell(fila, columna, data['totales'][mes['value']])
    hoja['U4'] = data['year']
    hoja['U2'] = hoja['U3'] = data['total']
    for fila in data['filas']:
        n = fila['fila_excel']
        for columna, campo in enumerate(campos, 1):
            if fila.get(campo):
                celda = hoja.cell(n, columna, fila[campo])
                celda.data_type = 's'
        for columna, mes in enumerate(data['meses'], 8):
            hoja.cell(n, columna, fila['meses'][mes['value']]).number_format = '#,##0.00'
        hoja.cell(n, 21, fila['total']).number_format = '#,##0.00'
    for celda in hoja[4][:21]:
        celda.fill = PatternFill('solid', fgColor='1E3A5F')
        celda.font = Font(bold=True, color='FFFFFF')
    for columna in range(1, 22):
        hoja.column_dimensions[get_column_letter(columna)].width = 25 if columna <= 7 else 18
    hoja.freeze_panes = 'H5'
    hoja.auto_filter.ref = f'A4:U{max((fila["fila_excel"] for fila in data["filas"]), default=4)}'
    return hoja
