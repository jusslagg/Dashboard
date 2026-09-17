"""Verifica la agrupación que alimenta Facturación por Cliente."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import Facturacion2026, Usuario
from app.routes import normalizar_header, resumen_dashboard


app = create_app()
app.config['TESTING'] = True

with app.app_context(), app.test_client() as client:
    usuario = Usuario.query.filter_by(activo=True).filter(
        Usuario.rol.in_(('Admin', 'Full'))
    ).first()
    assert usuario, 'No hay un usuario activo con acceso al dashboard'
    with client.session_transaction() as session:
        session['usuario_id'] = usuario.id

    response = client.get('/api/por-cliente')
    assert response.status_code == 200, response.get_data(as_text=True)
    clientes = response.get_json()['clientes']
    personal = [item for item in clientes if item['cliente'] == 'Personal']
    assert len(personal) == 1
    assert not any(item['cliente'].lower().startswith('personal ') for item in clientes)
    assert any(item['cliente'] == 'Santander' for item in clientes)

    registros_personal = [
        item for item in Facturacion2026.query.all()
        if normalizar_header(item.cliente).startswith('personal')
    ]
    assert {item.cliente for item in registros_personal} == {'Personal'}
    tipos_personal = {item.tipo_negocio for item in registros_personal}
    assert tipos_personal <= {
        'Personal CX', 'Personal SMB', 'Personal Soporte', 'Personal PPAY',
    }
    assert {'Personal CX', 'Personal SMB', 'Personal Soporte'} <= tipos_personal
    total_esperado = resumen_dashboard(registros_personal)['total_real']
    assert personal[0]['total_real'] == total_esperado

    totales = [float(item['total_real'] or 0) for item in clientes]
    assert totales == sorted(totales, reverse=True)
    pagina = client.get('/')
    assert pagina.status_code == 200
    html = pagina.get_data(as_text=True)
    assert 'id="contenedorGraficoClientes"' in html
    assert 'const ordenados = [...clientes].sort' in html
    assert 'autoSkip: false' in html
    posicion_santander = next(
        indice for indice, item in enumerate(clientes, start=1)
        if item['cliente'] == 'Santander'
    )
    print({
        'personal_unificado': personal[0]['total_real'],
        'variantes_incluidas': sorted({item.cliente for item in registros_personal}),
        'tipos_negocio': sorted(tipos_personal),
        'santander_posicion': posicion_santander,
        'clientes_ordenados': len(clientes),
    })
