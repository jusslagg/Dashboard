"""Orden y referencias estables de la hoja RESUMEN del libro operativo."""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path

from app.models import _clave_nombre


@lru_cache(maxsize=1)
def formato():
    return json.loads((Path(__file__).parent / 'data' / 'formato_resumen.json').read_text(encoding='utf-8'))


def construir_apoyo_resumen(data):
    """Valores de las claves operativas que documentan el subtotal CCE."""
    from app.routes import normalizar_nombre_variable
    def clave(valor):
        return _clave_nombre(normalizar_nombre_variable(str(valor or '')).replace(' nocturnas', ' nocturnidad'))
    meses = [item['value'] for item in data.get('meses', [])]
    lineas = formato().get('apoyo', [])
    claves = {clave(item['valores'][3]) for item in lineas if item['fila'] in range(6, 17)}
    pares = {(clave(cliente), clave(operativa)) for cliente, operativa in formato().get('pares_conocidos', [])}
    acumulado = defaultdict(float)
    for fila in data.get('filas', []):
        if fila.get('tipo') == 'total_site':
            continue
        for origen in fila.get('origenes', []):
            nombre = str(origen.get('campania') or '')
            operativa = clave(nombre)
            cliente = clave(origen.get('cliente'))
            if nombre.lower().endswith(' nocturnidad') and (cliente, operativa) not in pares:
                operativa = clave(nombre[:-len(' nocturnidad')])
            if operativa in claves and (not pares or (cliente, operativa) in pares):
                acumulado[operativa] += sum(float(fila.get('meses', {}).get(mes, 0) or 0) for mes in meses)
    return {item['fila']: acumulado[clave(item['valores'][3])]
            for item in lineas if item['fila'] in range(6, 17)}


def construir_formato_resumen(data):
    # Importación diferida: routes también utiliza este módulo.
    from app.routes import normalizar_nombre_variable

    def clave(valor):
        nombre = normalizar_nombre_variable(str(valor or '')).replace(' nocturnas', ' nocturnidad')
        return _clave_nombre(nombre)

    meses = [item['value'] for item in data.get('meses', [])]
    formato_actual = formato()
    definiciones = {fila['fila']: fila for fila in formato_actual['filas']}
    universo = {(f['tabla'] if f['tabla'] != 'Unificado' else 'Next Gen', clave(f['operativa']))
                for fila in definiciones.values() for f in fila['fuentes']}
    valores = defaultdict(lambda: {mes: 0.0 for mes in meses})
    clientes = defaultdict(set)
    conocidas = {clave(nombre) for nombre in formato_actual.get('operativas_conocidas', [])}
    pares_conocidos = {(clave(cliente), clave(operativa)) for cliente, operativa in formato_actual.get('pares_conocidos', [])}
    adicionales = {}
    for fila in data.get('filas', []):
        if fila.get('tipo') == 'total_site':
            continue
        concepto = fila.get('concepto')
        tabla = ('Facturacion Horas' if concepto in ('Horas', 'Fijo mensual') else
                 'Variable' if concepto == 'Variable' else
                 'Next Gen' if concepto == 'Next Gen' else 'Tarifacion')
        for origen in fila.get('origenes', []):
            nombre = str(origen.get('campania') or '')
            operativa = clave(nombre)
            cliente_origen = clave(origen.get('cliente'))
            if (nombre.lower().endswith(' nocturnidad') and
                    ((pares_conocidos and (cliente_origen, operativa) not in pares_conocidos) or
                     (not pares_conocidos and (tabla, operativa) not in universo))):
                operativa = clave(nombre[:-len(' nocturnidad')])
                nombre = nombre[:-len(' nocturnidad')]
            identidad = (cliente_origen, operativa)
            es_adicional = operativa and (identidad not in pares_conocidos if pares_conocidos else operativa not in conocidas)
            if not es_adicional:
                for mes in meses:
                    valores[(tabla, operativa)][mes] += float(fila.get('meses', {}).get(mes, 0) or 0)
                clientes[(tabla, operativa)].add(fila.get('cliente') or origen.get('cliente') or '')
            else:
                grupo = adicionales.setdefault(identidad, {'cliente': origen.get('cliente') or fila.get('cliente') or '',
                    'campania': nombre, 'site': fila.get('site') or '',
                    'orden_alta': fila.get('orden_alta'),
                    'conceptos': {tabla: {mes: 0.0 for mes in meses} for tabla in
                                  ('Facturacion Horas', 'Variable', 'Next Gen', 'Tarifacion')}})
                if fila.get('orden_alta'):
                    grupo['orden_alta'] = min(grupo.get('orden_alta') or fila['orden_alta'], fila['orden_alta'])
                for mes in meses:
                    grupo['conceptos'][tabla][mes] += float(fila.get('meses', {}).get(mes, 0) or 0)

    calculados = {}
    def calcular(numero):
        if numero in calculados:
            return calculados[numero]
        definicion = definiciones[numero]
        resultado = {mes: 0.0 for mes in meses}
        referencias = definicion.get('referencias', [])
        if referencias:
            for ref in referencias:
                for mes, importe in calcular(ref).items():
                    resultado[mes] += importe
        elif definicion.get('fuentes'):
            fuentes = set()
            for fuente in definicion['fuentes']:
                operativa = clave(fuente['operativa'])
                if fuente['tabla'] == 'Unificado' and str(definicion.get('concepto') or '').lower() == 'total':
                    fuentes.update((tabla, operativa) for tabla in ('Facturacion Horas', 'Variable', 'Next Gen', 'Tarifacion'))
                else:
                    fuentes.add(('Next Gen' if fuente['tabla'] == 'Unificado' else fuente['tabla'], operativa))
            for fuente in fuentes:
                for mes in meses:
                    resultado[mes] += valores[fuente][mes]
        calculados[numero] = resultado
        return resultado

    clientes_por_grupo = defaultdict(set)
    for definicion in definiciones.values():
        grupo = (definicion.get('site') or '', definicion.get('campania') or '')
        for fuente in definicion['fuentes']:
            if fuente.get('cliente'):
                clientes_por_grupo[grupo].add(str(fuente['cliente']))
    salida = []
    total_cat = {mes: 0.0 for mes in meses}
    for numero, definicion in definiciones.items():
        concepto = str(definicion.get('concepto') or '')
        nombre = str(definicion.get('campania') or '')
        importe = calcular(numero)
        c = concepto.lower()
        tipo = ('total_grupo' if numero == 26 else 'total_campania' if c == 'total' else
                'total_detalle' if 'incluido' in c else 'concepto')
        if c == 'total':
            for mes in meses:
                total_cat[mes] += importe[mes]
        asociados = set()
        for fuente in definicion['fuentes']:
            tabla = 'Next Gen' if fuente['tabla'] == 'Unificado' else fuente['tabla']
            asociados.update(clientes[(tabla, clave(fuente['operativa']))])
        fuentes_grupo = clientes_por_grupo[(definicion.get('site') or '', nombre)]
        cliente = (sorted(asociados)[0] if len(asociados) == 1 else
                   sorted(fuentes_grupo)[0] if len(fuentes_grupo) == 1 else nombre)
        salida.append({'fila_excel': numero, 'site': definicion.get('site') or '',
            'cliente': cliente, 'concepto': concepto, 'campania': nombre, 'tipo': tipo,
            'incluido': 233 <= numero <= 237 or 243 <= numero <= 252,
            'meses': {mes: round(importe[mes], 10) for mes in meses},
            'total': round(sum(importe.values()), 10)})
    siguiente_fila = 264  # Las filas 258:262 pertenecen al control del libro.
    for grupo in sorted(adicionales.values(), key=lambda item: item['orden_alta'] or '9999'):
        total = {mes: 0.0 for mes in meses}
        for tabla, concepto in (('Facturacion Horas', 'Horas'), ('Variable', 'Variable Productividad'),
                                ('Next Gen', 'Next Gen'), ('Tarifacion', 'Tarifacion + otros')):
            importe = grupo['conceptos'][tabla]
            for mes in meses:
                total[mes] += importe[mes]
            salida.append({'fila_excel': siguiente_fila, 'site': grupo['site'], 'cliente': grupo['cliente'],
                'concepto': concepto, 'campania': grupo['campania'], 'tipo': 'concepto',
                'meses': {mes: round(importe[mes], 10) for mes in meses}, 'total': round(sum(importe.values()), 10)})
            siguiente_fila += 1
        for mes in meses:
            total_cat[mes] += total[mes]
        salida.append({'fila_excel': siguiente_fila, 'site': grupo['site'], 'cliente': grupo['cliente'],
            'concepto': 'Total', 'campania': grupo['campania'], 'tipo': 'total_campania',
            'meses': {mes: round(total[mes], 10) for mes in meses}, 'total': round(sum(total.values()), 10)})
        siguiente_fila += 1
    salida.insert(0, {'fila_excel': 4, 'site': '', 'cliente': '', 'concepto': '',
        'campania': 'TOTAL CAT', 'tipo': 'total_cat',
        'meses': {mes: round(total_cat[mes], 10) for mes in meses}, 'total': round(sum(total_cat.values()), 10)})
    return salida
