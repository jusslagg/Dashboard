"""Exercise API and workbook direction filters on the isolated verification DB."""
from io import BytesIO
from pathlib import Path
import ast
import runpy
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

ROOT = Path(__file__).resolve().parents[1]
baseline = (ROOT / '.cache' / 'notificaciones-routes-baseline.py').read_text(encoding='utf-8-sig')
current = (ROOT / 'app/routes.py').read_text(encoding='utf-8-sig')
def function_code(source, name):
    tree = ast.parse(source)
    item = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, item)
for name in ('construir_notificaciones_proyecciones', 'consolidar_notificaciones_por_cliente', 'lectura_cambio_proyeccion'):
    assert function_code(baseline, name) == function_code(current, name), name

scope = runpy.run_path(str(ROOT / 'scripts/verificar_seleccion_multiple.py'))
app = scope['app']
from app.models import Usuario
from app.routes import filtrar_notificaciones_proyecciones
fixtures = [dict(mes='2026-01', estado='positiva', impacto_facturacion=0, metricas_cambiadas=[], site='A', cliente='A', campania='A', detalle=''),
            dict(mes='2026-02', estado='mixta', impacto_facturacion=5, metricas_cambiadas=[], site='A', cliente='B', campania='B', detalle=''),
            dict(mes='2026-03', estado='negativa', impacto_facturacion=-5, metricas_cambiadas=[], site='A', cliente='C', campania='C', detalle='')]
assert filtrar_notificaciones_proyecciones(fixtures, MultiDict([('direccion_importe', 'sin_impacto')])) == fixtures[:1]
assert filtrar_notificaciones_proyecciones(fixtures, MultiDict([('direccion_importe', 'sube'), ('direccion_importe', 'baja')])) == fixtures[1:]
assert filtrar_notificaciones_proyecciones(fixtures, MultiDict([('estado', 'positiva')])) == fixtures[:1]
with app.app_context(), app.test_client() as client:
    user = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
    all_items = client.get('/api/notificaciones-proyecciones?year=2026').get_json()['notificaciones']
    for direction in ('sube', 'baja', 'sin_impacto'):
        query = 'year=2026&direccion_importe=' + direction
        data = client.get('/api/notificaciones-proyecciones?' + query).get_json()
        expected = [item for item in all_items if ('sube' if item['impacto_facturacion'] > .005 else 'baja' if item['impacto_facturacion'] < -.005 else 'sin_impacto') == direction]
        assert data['notificaciones'] == expected
        response = client.get('/api/notificaciones-proyecciones/exportar?' + query)
        assert response.status_code == 200
        book = load_workbook(BytesIO(response.data))
        sheet = book['REPORTE']
        assert sheet.max_row - 1 == len(expected)
        assert abs(sum(row[8] or 0 for row in list(sheet.values)[1:]) - sum(item['impacto_facturacion'] for item in expected)) < .01
        assert book['COMO LEER']['B1'].value
print('OK: cálculos originales intactos; filtros de dirección, API, filas e importes Excel coinciden; filtro legado conservado.')
