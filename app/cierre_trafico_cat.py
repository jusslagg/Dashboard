"""Lectura de los resúmenes de cierre de tráfico CAT."""
import io
import math
from datetime import date
from openpyxl import load_workbook


# Nombres usados en los resúmenes de tráfico y en Nombre Proforma.
NOMBRES = {
    'Resumen': {
        'especializada movil': 'ISLA ESPECIALIZADA MOVIL',
        'ventas out': 'VENTAS OUT CABLE',
        'cat vtas wsp hogares': 'VENTAS WHATSAPP HOGARES',
        'cat retencion cable': 'RETENCION CABLE', 'cat abonos': 'ABONOS',
        'cat abonos validaciones': 'ABONOS VALIDACIONES',
        'cat ws movil': 'WS MOVIL', 'cat ws morosidad': 'WS MOROSIDAD',
        'comdata customer open': 'CUSTOMER OPEN',
        'cat customer convergente': 'CUSTOMER CONVERGENTE',
        'cat ws convergente': 'WS CONVERGENTE', 'cat cust onboarding': 'CUSTOMER ONBOARDING',
    },
    'Resumen Pay': {
        'pay digital': 'PERSONAL PAY DIGITAL', 'pay login & onboarding': 'PAY LOGING & ONBOARDING',
    },
    'Resumen SMB': {
        'ventas in crecimiento': 'VENTAS SMB', 'ventas out': 'VENTAS OUT SMB',
        'ventas whatsapp': 'VENTAS WHATSAPP SMB',
        'account executive smb': 'ISLA ACCOUNT EXECUTIVE (AE) TELEFONICO SMB',
        'wa account executive': 'ISLA ACCOUNT EXECUTIVE (AE) DIGITAL SMB',
        'ventas sd snb': 'OUT SDR/BDR PIC SMB', 'wa ventas sd': 'OUT SDR/BDR DIGITAL SMB',
    },
}


def numero(valor, hoja, fila):
    if type(valor) not in (float, int) or not math.isfinite(valor):
        raise ValueError(f'{hoja}, fila {fila}: valor pendiente o no numérico ({valor}).')
    return valor


def leer_resumen(hoja, nombre, normalizar, tipo_hora):
    pay = nombre == 'Resumen Pay'
    i = 3 if pay else 2
    cuadro = 7 if pay else 4
    bloques = []
    actual = None
    encabezado = False
    for fila in hoja.iter_rows(max_col=22):
        jornada = normalizar(fila[i].value)
        if jornada == 'tipo hora':
            encabezado = (normalizar(fila[i+1].value) == 'horas brutas'
                          and normalizar(fila[cuadro].value) == 'horas cuadro'
                          and normalizar(fila[13 if pay else 8].value) == 'hs a liquidar brutas'
                          and normalizar(fila[17 if pay else 10].value).startswith('penalidad adhesion'))
            continue
        if jornada not in ('normal', 'nocturna', 'feriado'):
            continue
        if not encabezado:
            raise ValueError(f'{nombre}: revise las columnas de horas y penalidad por adhesión.')
        if fila[i-1].value:
            actual = {'nombre': str(fila[i-1].value).strip(), 'filas': {}, 'peso': None}
            bloques.append(actual)
            if '%' in fila[cuadro].number_format:
                actual['peso'] = numero(fila[cuadro].value, nombre, fila[i].row)
            else:
                actual['penalidad'] = numero(fila[17 if pay else 10].value, nombre, fila[i].row)
                if pay:
                    actual['penalidad_no_prime'] = numero(fila[19].value, nombre, fila[i].row)
        if actual is None or jornada in actual['filas']:
            raise ValueError(f'{nombre}: jornada sin campaña o duplicada.')
        actual['filas'][jornada] = fila
    salida = {}
    padre = None
    pesos = []
    for n, bloque in enumerate(bloques):
        peso = bloque['peso']
        if peso is None:
            if pesos and not math.isclose(sum(pesos), 1, abs_tol=0.000001):
                raise ValueError(f'{nombre}: la distribución de {padre["nombre"]} no suma 100 %.')
            pesos = []
            padre = bloque
            if n + 1 < len(bloques) and bloques[n+1]['peso'] is not None:
                continue
        else:
            pesos.append(numero(peso, nombre, bloque['filas']['normal'][i].row))
        if padre is None or set(bloque['filas']) != set(padre['filas']):
            raise ValueError(f'{nombre}: distribución de jornadas incompleta.')
        campania = NOMBRES[nombre].get(normalizar(bloque['nombre']), bloque['nombre'])
        for jornada, fila in bloque['filas'].items():
            row = fila[i].row
            brutas = numero(fila[i+1].value, nombre, row)
            horas = numero(padre['filas'][jornada][cuadro].value, nombre, row)
            adh = padre['penalidad']
            if pay and adh != padre['penalidad_no_prime'] and brutas:
                prime = numero(fila[5].value, nombre, row)
                no_prime = numero(fila[6].value, nombre, row)
                adh = (prime * adh + no_prime * padre['penalidad_no_prime']) / brutas
            vh = tipo_hora(jornada)
            clave = normalizar(campania), normalizar(vh)
            if clave in salida:
                raise ValueError(f'{nombre}: se repite {campania} / {vh}.')
            liquidar = fila[13 if pay else 8].value
            if brutas == 0 and liquidar == '#DIV/0!':
                liquidar = 0
            salida[clave] = dict(campania=campania, tipo_vh=vh, hojas=[nombre],
                                 brutas_con_tope=numero(liquidar, nombre, row),
                                 definitiva=horas * (1 if peso is None else peso), brutas=brutas, adh=adh)
    if pesos and not math.isclose(sum(pesos), 1, abs_tol=0.000001):
        raise ValueError(f'{nombre}: la distribución de {padre["nombre"]} no suma 100 %.')
    if not salida:
        raise ValueError(f'{nombre}: sin campañas con jornadas reconocidas.')
    return salida


def leer_cierre_cat(archivo, normalizar, tipo_hora):
    libro = load_workbook(io.BytesIO(archivo), read_only=True, data_only=True)
    try:
        hojas = {normalizar(h.title): h for h in libro}
        if 'resumen pay' in hojas or 'resumen smb' in hojas:
            grupos = {'Masivo': ['Resumen', 'Resumen SMB'], 'Personal Pay': ['Resumen Pay']}
        elif 'resumen' in hojas and 'soporte' in hojas:
            grupos = {'Soporte': ['Resumen']}
        else:
            return None
        periodos = set()
        for h in libro:
            if normalizar(h.title).startswith('resumen'):
                continue
            rows = h.iter_rows(min_row=3, max_col=8, values_only=True)
            header = next(rows, ())
            if len(header) < 8 or normalizar(header[2]) != 'fecha':
                continue
            for r in rows:
                if not isinstance(r[2], date):
                    break
                if r[6] or r[7]:
                    periodos.add(r[2].strftime('%Y%m'))
        if len(periodos) != 1:
            raise ValueError('Se requiere un único mes con actividad en el detalle por intervalo.')
        lotes = []
        for grupo, nombres in grupos.items():
            detalle = {}
            for nombre in nombres:
                if normalizar(nombre) not in hojas:
                    raise ValueError(f'Falta la hoja {nombre} en el cierre.')
                nuevas = leer_resumen(hojas[normalizar(nombre)], nombre, normalizar, tipo_hora)
                if detalle.keys() & nuevas.keys():
                    raise ValueError(f'{nombre}: hay campañas duplicadas entre los resúmenes.')
                detalle.update(nuevas)
            lotes.append((grupo, detalle, nombres))
        return periodos.pop(), lotes
    finally:
        libro.close()
