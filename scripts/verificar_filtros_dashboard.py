"""Audita los filtros del dashboard sin modificar la base de datos."""
from pathlib import Path
import sys
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.models import Usuario  # noqa: E402


app = create_app()
app.config['TESTING'] = True

campos = {
    'year': ('years', lambda fila, valor: str(fila.get('mes', '')).startswith(f'{valor}-')),
    'mes': ('meses', lambda fila, valor: fila.get('mes') == valor),
    'cliente': ('clientes', lambda fila, valor: fila.get('cliente') == valor),
    'gerente': ('gerentes', lambda fila, valor: fila.get('gerente') == valor),
    'jefe_site': ('jefes_site', lambda fila, valor: fila.get('jefe_site') == valor),
    'campania': ('campanias', lambda fila, valor: fila.get('campania') == valor),
    'subcampania': ('subcampanias', lambda fila, valor: fila.get('subcampania') == valor),
    'tipo_negocio': ('tipos_negocio', lambda fila, valor: fila.get('tipo_negocio') == valor),
}

with app.app_context():
    usuario = Usuario.query.filter_by(activo=True).filter(
        Usuario.rol.in_(('Admin', 'Full'))
    ).first()
    assert usuario, 'No hay un usuario activo con alcance total para auditar filtros'

    with app.test_client() as cliente_http:
        with cliente_http.session_transaction() as sesion:
            sesion['usuario_id'] = usuario.id

        respuesta = cliente_http.get('/api/filtros')
        assert respuesta.status_code == 200
        opciones = respuesta.get_json()['filtros']
        assert 'Sin gerencia' in opciones.get('gerentes', []), (
            'Datos Maestros contiene Sin gerencia pero no aparece en el filtro'
        )
        sin_gerencia = cliente_http.get('/api/por-cliente?gerente=Sin+gerencia').get_json()['clientes']
        assert any(item['cliente'] == 'Santander' and item['registros'] > 0 for item in sin_gerencia), (
            'La facturación Santander / Sin gerencia no aparece con valores reales'
        )
        isla_query = urlencode({'gerente': 'Sin gerencia', 'campania': 'Isla Prevención de fraude'})
        filas_isla = cliente_http.get(f'/api/datos?{isla_query}').get_json()['data']
        assert len(filas_isla) == 21 and all(fila['cliente'] == 'Santander' for fila in filas_isla)

        for parametro, (clave_opciones, coincide) in campos.items():
            valores = opciones.get(clave_opciones) or []
            assert valores, f'El filtro {parametro} no tiene opciones'
            valor = valores[0]
            query = urlencode([(parametro, valor)])
            datos = cliente_http.get(f'/api/datos?{query}')
            assert datos.status_code == 200
            filas = datos.get_json()['data']
            assert filas, f'El filtro {parametro}={valor} no devolvió registros'
            assert all(coincide(fila, valor) for fila in filas), (
                f'El filtro {parametro} devolvió registros fuera de {valor}'
            )
            for endpoint, clave in (
                ('/api/kpis', 'kpis'), ('/api/grafico', 'datos'),
                ('/api/resumen', 'resumen'), ('/api/por-cliente', 'clientes'),
                ('/api/alertas', 'alertas'),
            ):
                resultado = cliente_http.get(f'{endpoint}?{query}')
                assert resultado.status_code == 200, f'{endpoint} falló con {parametro}'
                cuerpo = resultado.get_json()
                assert cuerpo.get('success') is True and clave in cuerpo

        clientes = (opciones.get('clientes') or [])[:2]
        if len(clientes) == 2:
            query = urlencode([('cliente', valor) for valor in clientes])
            filas = cliente_http.get(f'/api/datos?{query}').get_json()['data']
            assert filas and {fila['cliente'] for fila in filas}.issubset(set(clientes))

        exportacion = cliente_http.get('/api/exportar_excel?' + urlencode([
            ('year', opciones['years'][0]),
            ('cliente', opciones['clientes'][0]),
        ]))
        assert exportacion.status_code == 200
        assert 'application/vnd.ms-excel' in exportacion.headers.get('Content-Type', '')

print(
    'Filtros dashboard OK: 8 dimensiones, selección múltiple, '
    '5 vistas derivadas y exportación Excel verificadas.'
)
