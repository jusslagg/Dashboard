"""Compara cada cliente/mes del comparativo con las fuentes actuales, sin escribir datos."""
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import Facturacion2026
from app.routes import (construir_proyectado_vs_facturado_data, construir_resumen_proyeccion_data,
                        consolidar_resumen_proyeccion, facturacion_por_anio, normalizar_header)

app = create_app()
with app.app_context():
    facturas = facturacion_por_anio(Facturacion2026.query, 2026).all()
    nombres = {normalizar_header(f.cliente) for f in facturas}
    equivalencias = {
        'banco bice': 'bice', 'bsf': 'bsf carrefour', 'banco credicoop': 'credicoop',
        'galicia seguros': 'galicia', 'jonhson & jonhson': 'johnson & johnson',
        'bbva openpay': 'openpay', 'apm - terminal 4': 'terminal 4',
        'santander getnet': 'santander', 'personal cx': 'personal',
        'personal smb': 'personal', 'personal soporte': 'personal',
    }
    esperado = defaultdict(lambda: [0., 0., 0.])
    for f in facturas:
        entrada = esperado[(f.mes, normalizar_header(f.cliente))]
        entrada[0] += f.total_teorico or 0
        entrada[2] += f.total_dashboard or 0
    resumen = consolidar_resumen_proyeccion(construir_resumen_proyeccion_data(2026))
    for fila in resumen['filas']:
        if fila.get('tipo') != 'detalle':
            continue
        cliente = normalizar_header(fila['cliente'])
        if cliente not in nombres:
            cliente = equivalencias.get(cliente, cliente)
        for mes, valor in fila['meses'].items():
            if valor:
                esperado[(mes, cliente)][1] += valor
    comparativo = construir_proyectado_vs_facturado_data(2026)['filas']
    obtenido = {(f['mes'], normalizar_header(f['cliente'])): [f['teorico'], f['proyectado'], f['facturado']]
                for f in comparativo}
    assert len(obtenido) == len(comparativo), 'Hay clientes duplicados en el mismo mes'
    errores = []
    for clave in sorted(set(esperado) | set(obtenido)):
        for i, nombre in enumerate(('teórico', 'proyectado', 'facturado')):
            a = esperado.get(clave, [0, 0, 0])[i]
            b = obtenido.get(clave, [0, 0, 0])[i]
            if abs(a - b) > .01:
                errores.append((clave, nombre, a, b))
    print(f'{len(obtenido)} combinaciones cliente/mes; {len(errores)} diferencias con las fuentes actuales')
    for error in errores[:30]:
        print(error)
    if errores:
        raise SystemExit(1)
