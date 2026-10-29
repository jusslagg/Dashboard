"""Read-only drilldowns using exactly the existing dashboard alert criteria."""
TIPOS_APERTURA = {'cumplimiento_bajo', 'debajo_objetivo', 'negativo', 'horas', 'riesgo', 'desvio', 'sin_facturacion'}


def apertura_alerta(registros, tipo, asignaciones=()):
    from .routes import resumen_dashboard, resumen_registros
    summarize = resumen_dashboard if tipo == 'desvio' else resumen_registros
    registros = list(registros)
    if tipo == 'sin_facturacion':
        pairs = sorted({(item.cliente, item.campania) for item in asignaciones}) if not registros else []
        rows = [{'cliente':client, 'campania':campaign, 'periodo':None,'meses':[],
                'desvio':None, 'cumplimiento':None, 'horas_objetivo':None, 'horas_facturadas':None}
                for client,campaign in pairs]
        return {'success':True, 'filas':rows, 'clientes':[
            {'cliente':client,'desvio':None,'cumplimiento':None,'horas_objetivo':None,'horas_facturadas':None,
             'periodo':None,'campanias':[row for row in rows if row['cliente']==client]}
            for client in sorted({row['cliente'] for row in rows})],
            'criterio':'Asociaciones de Datos Maestros sin facturación para la selección actual.'}
    clients = {}
    for item in registros:
        clients.setdefault(item.cliente,[]).append(item)
    risk = {name for name,items in clients.items() if resumen_registros(items)['porcentaje_cumplimiento'] < 95}
    total = summarize(registros)
    active = {'cumplimiento_bajo':bool(registros) and total['porcentaje_cumplimiento'] < 95,
              'debajo_objetivo':95 <= total['porcentaje_cumplimiento'] < 100,
              'negativo':total['desvio'] < 0, 'horas':any(item.horas_facturadas > item.horas_objetivo for item in registros),
              'riesgo':bool(risk), 'desvio':bool(registros)}
    groups = {}
    excess = {(item.cliente,item.campania) for item in registros if item.horas_facturadas > item.horas_objetivo}
    if active.get(tipo):
        for item in registros:
            if tipo == 'riesgo' and item.cliente not in risk:
                continue
            groups.setdefault((item.cliente, item.campania),[]).append(item)
    rows = []
    all_campaigns = []
    def metrics(items):
        summary = summarize(items)
        return {'desvio':summary['desvio'],
                'cumplimiento':summary['porcentaje_cumplimiento'] if summary['total_teorico'] > 0 else None,
                'horas_objetivo':summary['horas_objetivo'],'horas_facturadas':summary['horas_facturadas']}
    for (client,campaign),items in groups.items():
        summary = summarize(items)
        months = {}
        for item in items:
            months.setdefault(item.mes,[]).append(item)
        ordered = sorted(months)
        row = {'cliente':client,'campania':campaign,**metrics(items),
                     'periodo':ordered[0] if len(ordered)==1 else f'{ordered[0]} a {ordered[-1]}',
                     'meses':[{'mes':month,**metrics(months[month])} for month in ordered]}
        all_campaigns.append(row)
        if tipo == 'horas' and (client,campaign) not in excess:
            continue
        if tipo == 'negativo' and summary['desvio'] >= 0:
            continue
        if tipo in ('cumplimiento_bajo','debajo_objetivo') and summary['porcentaje_cumplimiento'] >= (95 if tipo == 'cumplimiento_bajo' else 100):
            continue
        rows.append(row)
    rows.sort(key=lambda item:(-abs(item['desvio']),item['cliente'],item['campania'] or ''))
    criteria = {
        'desvio':'Mismo desvío comparable del dashboard. Clientes de mayor a menor pérdida acumulada; las compensaciones positivas aparecen al final. Los importes en cero se ocultan.',
        'cumplimiento_bajo':'Campañas cuyo cumplimiento acumulado está por debajo del 95% para el período filtrado.',
        'debajo_objetivo':'Campañas cuyo cumplimiento acumulado está por debajo del 100% para el período filtrado.',
        'negativo':'Campañas con desvío acumulado negativo, incluyendo la compensación entre sus meses positivos y negativos. Esta lista no es el saldo neto de todas las campañas del dashboard.',
        'horas':'Campañas con al menos un registro que supera las horas objetivo. El acumulado incluye todos sus registros del período, también los que están por debajo.',
        'riesgo':'Acumulado por campaña de clientes cuyo cumplimiento está por debajo del 95%. Una campaña individual puede estar en positivo.',
    }
    accounts = []
    if active.get(tipo):
        for client,items in clients.items():
            summary = summarize(items)
            if tipo in ('riesgo','cumplimiento_bajo') and summary['porcentaje_cumplimiento'] >= 95:
                continue
            if tipo == 'debajo_objetivo' and summary['porcentaje_cumplimiento'] >= 100:
                continue
            if tipo == 'negativo' and summary['desvio'] >= 0:
                continue
            if tipo == 'horas' and not any(name==client for name,_ in excess):
                continue
            campaigns = sorted((row for row in all_campaigns if row['cliente']==client),key=lambda row:-abs(row['desvio']))
            months = sorted({item.mes for item in items})
            accounts.append({'cliente':client,**metrics(items),
                             'periodo':months[0] if len(months)==1 else f'{months[0]} a {months[-1]}',
                             'campanias':campaigns})
    accounts.sort(key=lambda item:(-abs(item['desvio']),item['cliente']))
    if tipo == 'desvio':
        accounts.sort(key=lambda item:(item['desvio'],item['cliente']))
        for account in accounts:
            account['campanias'].sort(key=lambda item:(item['desvio'],item['campania'] or ''))
    if tipo == 'desvio':
        return {'success':True,'filas':rows,'clientes':accounts,
                'total_desvio':total['desvio'],'criterio_clientes':criteria[tipo],
                'criterio':criteria[tipo]}
    return {'success':True,'filas':rows,'clientes':accounts,
            'total_desvio':total['desvio'],
            'criterio_clientes':'Acumulado de esta alerta por cliente (Total Real menos Total Teórico). Al abrirlo se muestran todas sus campañas, incluidas las que compensan el desvío en sentido contrario.',
            'criterio':criteria[tipo] + ' Los importes conservan la regla de alertas: Total Real menos Total Teórico; no sustituyen el desvío comparable del indicador principal.'}
