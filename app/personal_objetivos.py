"""Las cuatro reglas de Objetivo Horas de la plantilla de Personal.

F de Auxiliar es planificación manual; H es el cierre. No se distribuye
planificación entre campañas ni se recortan los resultados negativos.
"""
from collections import defaultdict
import re


def regla_objetivo(formula, tipo):
    formula = str(formula or '').upper().replace('$', '').replace(' ', '')
    if re.fullmatch(r'=\+?H\d+', formula):
        return 'facturadas'
    if not formula and tipo.startswith('capacitaciones'):
        return 'facturadas'
    if tipo.startswith('diurnas'):
        # Ventas In/Out resta las otras jornadas también en el cierre.
        if re.search(r'\)-H\d+-H\d+\)$', formula):
            return 'diurnas_resta_cierre'
        return 'diurnas'
    return 'otras'


def reglas_plantilla(filas, normalizar):
    reglas = {}
    for fila in filas:
        if len(fila) > 6 and fila[3].get('v') and fila[6].get('f'):
            tipo = normalizar(fila[4].get('v'))
            reglas[(normalizar(fila[3]['v']), tipo)] = regla_objetivo(fila[6]['f'], tipo)
    return reglas


def recalcular_objetivos(filas_base, filas_auxiliar, reglas, normalizar, periodo,
                        mapa_campanias=None, periodos=None):
    """Actualiza G/S/T/U y sus fórmulas usando las mismas claves que SUMIFS.

Las asociaciones de Aux resuelven los nombres nuevos de Proforma. Los meses
sin cambios conservan el contenido importado. ``periodos=None`` calcula todo.
    """
    mapa_campanias = mapa_campanias or {}

    def campania(valor):
        clave = normalizar(valor)
        return normalizar(mapa_campanias.get(clave, valor))

    def numero(valor):
        # SUMIFS ignora celdas vacías y textos.
        return float(valor) if isinstance(valor, (int, float)) else 0.0

    auxiliar = defaultdict(lambda: [0.0, 0.0])
    nombres_auxiliar = defaultdict(set)
    for fila in filas_auxiliar[1:]:
        if len(fila) < 8:
            continue
        mes = periodo(fila[3].get('v'))
        nombre = fila[1].get('v')
        if not mes or not nombre:
            continue
        clave = (mes, campania(nombre), normalizar(fila[2].get('v')))
        auxiliar[clave][0] += numero(fila[5].get('v'))
        auxiliar[clave][1] += numero(fila[7].get('v'))
        nombres_auxiliar[clave].add(str(nombre))

    facturadas = defaultdict(float)
    for fila in filas_base[2:]:
        if len(fila) > 7:
            clave = (periodo(fila[5].get('v')), campania(fila[3].get('v')), normalizar(fila[4].get('v')))
            facturadas[clave] += numero(fila[7].get('v'))

    for n, fila in enumerate(filas_base[2:], start=3):
        if len(fila) < 21 or not fila[3].get('v'):
            continue
        mes = periodo(fila[5].get('v'))
        if not mes or (periodos is not None and mes not in periodos):
            continue
        tipo = normalizar(fila[4].get('v'))
        clave = (mes, campania(fila[3]['v']), tipo)
        regla = (regla_objetivo(fila[6]['f'], tipo) if fila[6].get('f')
                 else reglas.get((clave[1], tipo), regla_objetivo(None, tipo)))
        proyectada = normalizar(fila[15].get('v')) == 'proyectada'
        plan, cierre = auxiliar[clave]
        sufijo = ' ii' if tipo.endswith(' ii') else ''
        pares = [f'nocturnas{sufijo}', f'feriados{sufijo}']
        otras = sum(facturadas[(mes, clave[1], par)] for par in pares)

        def suma_aux(columna):
            nombres = sorted(nombres_auxiliar[clave]) or [str(fila[3]['v'])]
            return '+'.join(
                f'SUMIFS(\'Auxiliar Horas PLP masivo\'!{columna}:{columna},'
                f"'Auxiliar Horas PLP masivo'!D:D,F{n},"
                f"'Auxiliar Horas PLP masivo'!C:C,E{n},"
                f"'Auxiliar Horas PLP masivo'!B:B,\"{nombre.replace(chr(34), chr(34) * 2)}\")"
                for nombre in nombres
            )

        resta = ''.join(f'-SUMIFS(H:H,F:F,F{n},D:D,D{n},E:E,"{par}")' for par in pares)
        if not fila[6].get('f') and isinstance(fila[6].get('v'), (int, float)):
            # La plantilla también contiene objetivos fijados manualmente.
            objetivo, formula = numero(fila[6]['v']), None
        elif regla == 'facturadas':
            objetivo, formula = numero(fila[7].get('v')), f'=H{n}'
        elif regla.startswith('diurnas'):
            objetivo = plan - otras if proyectada else cierre - (otras if regla == 'diurnas_resta_cierre' else 0)
            formula = (f'=IF(P{n}="proyectada",{suma_aux("F")}{resta},'
                       f'{suma_aux("H")}{resta if regla == "diurnas_resta_cierre" else ""})')
        else:
            objetivo = numero(fila[7].get('v')) if proyectada else cierre
            formula = f'=IF(P{n}="proyectada",H{n},{suma_aux("H")})'
        importe = objetivo * numero(fila[8].get('v'))
        bono = numero(fila[16].get('v')) * objetivo - importe
        for indice, valor, formula_celda in (
            (6, objetivo, formula), (18, importe, f'=G{n}*I{n}'),
            (19, bono, f'=Q{n}*G{n}-S{n}'), (20, importe + bono, f'=S{n}+T{n}'),
        ):
            fila[indice].update(v=valor, t='numero')
            if formula_celda:
                fila[indice]['f'] = formula_celda
