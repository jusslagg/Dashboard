"""Read-only explanations built from the existing Facturación calculations."""

FILAS_DESVIO = [
    ('desvio_horas', 'Horas · desvío $', 'moneda', False),
    ('desvio_variable', 'Variable · desvío $', 'moneda', False),
    ('penalizaciones_bonos', 'Penalizaciones / bonos', 'moneda', False),
    ('ajuste_objetivo', 'Ajuste de objetivo importado', 'moneda', False),
    ('redondeo', 'Diferencia de redondeo', 'moneda', False),
    ('desvio_porcentaje', 'Desvío de facturación %', 'desvio_porcentaje', False),
    ('cumplimiento_facturacion', 'Cumplimiento de facturación %', 'cumplimiento', False),
    ('cumplimiento_horas', 'Cumplimiento de horas %', 'cumplimiento', False),
    ('cumplimiento_horas_adh', 'Cumplimiento horas netas / ADH %', 'cumplimiento', False),
    ('cumplimiento_valor_hora', 'Cumplimiento de valor hora %', 'cumplimiento', False),
    ('cumplimiento_bono', 'Cumplimiento de bonos %', 'cumplimiento', False),
    ('horas_objetivo', 'Horas objetivo', 'horas', True),
    ('horas_facturadas', 'Horas facturadas', 'horas', True),
    ('horas_penalizadas', 'Horas penalizadas', 'horas', True),
    ('total_teorico', 'Objetivo comparable $', 'importe', True),
    ('total_comparable', 'Facturado comparable $', 'importe', True),
    ('desvio', 'TOTAL DESVÍO', 'total', False),
]


def resumen_desvio(registros):
    from .routes import metricas_matriz, resumen_dashboard

    registros = list(registros)
    resumen = resumen_dashboard(registros)
    matriz = metricas_matriz(registros)
    objetivo = resumen['total_teorico']
    horas_objetivo = resumen['horas_objetivo']
    base = [item for item in registros if not item.es_next_gen]
    objetivo_bono = sum(item.objetivo_facturacion_bono for item in registros)
    objetivo_ajuste = round(matriz['horas_obj'] + matriz['variable_obj'] - objetivo, 2)
    componentes = matriz['desvio_horas_monto'] + matriz['desvio_variable'] + matriz['desvio_penalizaciones_bonos'] + objetivo_ajuste
    return {
        'desvio_horas': matriz['desvio_horas_monto'],
        'desvio_variable': matriz['desvio_variable'],
        'penalizaciones_bonos': matriz['desvio_penalizaciones_bonos'],
        'ajuste_objetivo': objetivo_ajuste,
        'redondeo': round(resumen['desvio'] - componentes, 2),
        'desvio_porcentaje': round(resumen['porcentaje_cumplimiento_facturacion'] - 100, 2) if objetivo > 0 else None,
        'cumplimiento_facturacion': resumen['porcentaje_cumplimiento_facturacion'] if objetivo > 0 else None,
        'cumplimiento_horas': resumen['porcentaje_cumplimiento_horas'] if horas_objetivo > 0 else None,
        'cumplimiento_horas_adh': resumen['porcentaje_cumplimiento_horas_adh'] if horas_objetivo > 0 else None,
        'cumplimiento_valor_hora': resumen['porcentaje_valor_hora'] if objetivo > 0 and resumen['horas_facturadas'] > 0 else None,
        'cumplimiento_bono': resumen['porcentaje_bono'] if objetivo_bono > 0 else None,
        'horas_objetivo': horas_objetivo,
        'horas_facturadas': resumen['horas_facturadas'],
        'horas_penalizadas': resumen['horas_penalizadas'],
        'total_teorico': objetivo,
        'total_comparable': round(sum(item.total_comparable for item in base), 2),
        'total_facturado': resumen['total_facturado'],
        'desvio': resumen['desvio'],
    }


def construir_dashboard_desvios(registros, argumentos):
    from .routes import normalizar_header

    registros = list(registros)

    def cuenta(item):
        return 'Personal' if normalizar_header(item.cliente).startswith('personal') else (item.cliente or 'Sin cliente')

    opciones = {
        'year': sorted({item.mes[:4] for item in registros}),
        'mes': sorted({item.mes for item in registros}),
        'cliente_grupo': sorted({cuenta(item) for item in registros}),
        **{campo: sorted({getattr(item, campo) for item in registros if getattr(item, campo)})
           for campo in ('gerente', 'jefe_site', 'campania')},
    }
    grupos = {}
    for registro in registros:
        grupos.setdefault(cuenta(registro), []).append(registro)
    direccion = argumentos.get('direccion', '')
    cliente = normalizar_header(argumentos.get('cliente_grupo', ''))
    buscar = normalizar_header(argumentos.get('buscar', ''))
    abrir_campanias = argumentos.get('apertura') == 'campanias' and bool(cliente)
    clientes = []
    visibles = []
    for nombre, items in grupos.items():
        if cliente and normalizar_header(nombre) != cliente:
            continue
        if buscar and buscar not in normalizar_header(nombre):
            continue
        resumen = resumen_desvio(items)
        signo = 'positivo' if resumen['desvio'] > 0.005 else 'negativo' if resumen['desvio'] < -0.005 else 'sin_desvio'
        if direccion and signo != direccion:
            continue
        por_mes = {}
        for item in items:
            por_mes.setdefault(item.mes, []).append(item)
        clientes.append({
            'cliente': nombre, 'registros': len(items), 'direccion': signo,
            'resumen': resumen,
            'meses': {mes: resumen_desvio(filas) for mes, filas in sorted(por_mes.items())},
        })
        if abrir_campanias:
            por_campania = {}
            for item in items:
                # Keep the missing-value group separate from an actual named campaign.
                por_campania.setdefault(item.campania or None, []).append(item)
            campanias = []
            for nombre_campania, registros_campania in por_campania.items():
                meses_campania = {}
                for item in registros_campania:
                    meses_campania.setdefault(item.mes, []).append(item)
                resumen_campania = resumen_desvio(registros_campania)
                campanias.append({
                    'campania': nombre_campania,
                    'nombre': nombre_campania or 'Sin campaña asignada',
                    'registros': len(registros_campania),
                    'resumen': resumen_campania,
                    'direccion': 'positivo' if resumen_campania['desvio'] > .005 else 'negativo' if resumen_campania['desvio'] < -.005 else 'sin_desvio',
                    'meses': {mes: resumen_desvio(filas) for mes, filas in sorted(meses_campania.items())},
                })
            clientes[-1]['campanias'] = sorted(campanias, key=lambda item: (-abs(item['resumen']['desvio']), item['nombre']))
        visibles.extend(items)
    clientes.sort(key=lambda item: (-abs(item['resumen']['desvio']), item['cliente']))
    years = opciones['year']
    meses = [{'value': f'{year}-{mes:02d}', 'label': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][mes - 1] + (f' {year}' if len(years) > 1 else '')}
             for year in years for mes in range(1, 13)]
    metricas = [item['resumen'] for item in clientes] + [values for item in clientes for values in item['meses'].values()]
    metricas.extend(values for item in clientes for campania in item.get('campanias', [])
                    for values in [campania['resumen'], *campania['meses'].values()])
    filas = [{'id': key, 'label': label, 'tipo': tipo, 'detalle': detalle}
             for key, label, tipo, detalle in FILAS_DESVIO
             if key not in ('ajuste_objetivo', 'redondeo') or any(abs(item[key]) >= 0.005 for item in metricas)]
    return {
        'success': True, 'clientes': clientes, 'totales': resumen_desvio(visibles),
        'meses': meses, 'opciones': opciones, 'filas': filas,
        'registros': len(visibles),
        'criterio': 'Desvío = Horas + Variable + Penalizaciones/Bonos + ajustes de objetivo y redondeo. Next Gen, tarifación y otros se informan en Total Facturado, pero no integran este desvío comparable.',
    }
