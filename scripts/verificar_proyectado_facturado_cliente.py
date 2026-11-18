"""Comprueba la conciliación por cliente sin modificar la base operativa."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from openpyxl import load_workbook

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.routes import construir_proyectado_vs_facturado_data
from app.directorio_export import crear_libro_directorio


def proyeccion(cliente, servicio, valor, mes='2026-08'):
    return {'tipo': 'detalle', 'cliente': cliente, 'campania': servicio,
            'site': 'Site', 'meses': {mes: valor}}


def facturacion(cliente, campania, teorico, facturado, mes='2026-08'):
    return SimpleNamespace(cliente=cliente, campania=campania, subcampania='Otra', mes=mes,
                           total_teorico=teorico, total_dashboard=facturado)


app = create_app()
with app.app_context():
    fuente = {'filas': [
        proyeccion('BBVA OPENPAY', 'Horas', 100), proyeccion('BBVA OPENPAY', 'Variable', 12),
        proyeccion('Personal', 'General', 200), proyeccion('Personal SMB', 'SMB', 40),
        proyeccion('Personal Soporte', 'Soporte', 30),
        proyeccion('Santander', 'Santander', 300), proyeccion('Santander Getnet', 'Getnet', 50),
        proyeccion('BANCO BICE', 'Bice', 50), proyeccion('BSF', 'Carrefour', 60),
        proyeccion('Banco Credicoop', 'Credicoop', 70),
        proyeccion('Galicia Seguros', 'Backoffice', 80),
        proyeccion('JONHSON & JONHSON', 'Johnson', 90),
        proyeccion('APM - TERMINAL 4', 'Terminal', 20),
        proyeccion('Cliente nuevo', 'Nuevo', 25, '2026-12'),
    ]}
    facturas = [
        facturacion('Openpay', 'Sin correspondencia de campaña', 80, 75),
        facturacion('Openpay', 'Otra campaña', 20, 17),
        facturacion('Personal', 'Un grupo', 100, 90), facturacion('Personal', 'Otro grupo', 40, 35),
        facturacion('Santander', 'Getnet', 40, 35), facturacion('Santander', 'Mixto', 80, 70),
        facturacion('BICE', 'BICE', 20, 19), facturacion('BSF Carrefour', 'BSF', 30, 25),
        facturacion('Credicoop', 'Banco Credicoop', 10, 8),
        facturacion('Galicia', 'Seguros', 10, 9),
        facturacion('Johnson & Johnson', 'Johnson', 9, 8),
        facturacion('TERMINAL 4', 'Terminal', 5, 4),
    ]
    with patch('app.routes.construir_resumen_proyeccion_data', return_value={}), \
         patch('app.routes.consolidar_resumen_proyeccion', return_value=fuente), \
         patch('app.routes.facturacion_por_anio', return_value=SimpleNamespace(all=lambda: facturas)):
        filas = construir_proyectado_vs_facturado_data(2026)['filas']
    por_cliente = {fila['cliente']: fila for fila in filas}
    assert len(filas) == len(por_cliente), 'Una fila por cliente y mes'
    assert por_cliente['Openpay']['proyectado'] == 112 and por_cliente['Openpay']['facturado'] == 92
    assert por_cliente['Personal']['proyectado'] == 270 and por_cliente['Personal']['facturado'] == 125
    assert por_cliente['Santander']['proyectado'] == 350 and por_cliente['Santander']['facturado'] == 105
    for cliente, valor in [('BICE', 50), ('BSF Carrefour', 60), ('Credicoop', 70), ('Galicia', 80),
                           ('Johnson & Johnson', 90), ('TERMINAL 4', 20)]:
        assert por_cliente[cliente]['proyectado'] == valor
    assert por_cliente['Cliente nuevo']['mes'] == '2026-12'
    assert all(set(fila) == {'cliente', 'mes', 'teorico', 'proyectado', 'facturado'} for fila in filas)
    assert sum(f['proyectado'] for f in filas) == sum(f['meses'][next(iter(f['meses']))] for f in fuente['filas'])
    assert sum(f['facturado'] for f in filas) == sum(f.total_dashboard for f in facturas)
    assert sum(f['teorico'] for f in filas) == sum(f.total_teorico for f in facturas)
    libro = load_workbook(crear_libro_directorio([('Proyectado vs Facturado', {
        'meses': ['2026-08', '2026-12'], 'filas': filas,
    })], 2026), data_only=True)
    celdas = [str(c.value) for hoja in libro for fila in hoja.iter_rows() for c in fila if c.value is not None]
    assert 'Detalle por cliente' in celdas
    assert 'Servicio' not in celdas and 'Site' not in celdas

    # Un cliente exacto siempre prevalece sobre una equivalencia histórica.
    facturas.append(facturacion('Santander Getnet', 'Independiente', 8, 7))
    with patch('app.routes.construir_resumen_proyeccion_data', return_value={}), \
         patch('app.routes.consolidar_resumen_proyeccion', return_value=fuente), \
         patch('app.routes.facturacion_por_anio', return_value=SimpleNamespace(all=lambda: facturas)):
        separados = {fila['cliente']: fila for fila in construir_proyectado_vs_facturado_data(2026)['filas']}
    assert separados['Santander']['proyectado'] == 300
    assert separados['Santander Getnet']['proyectado'] == 50
    print('OK: clientes, equivalencias, prioridades y conservación de los tres importes.')
