"""Verifica el resumen mensual y los KPIs de horas contra Facturación."""
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app import create_app  # noqa: E402
from app.models import Facturacion2026, Usuario  # noqa: E402


def verificar():
    app = create_app()
    with app.app_context():
        usuario = Usuario.query.filter_by(activo=True).first()
        registros = Facturacion2026.query.filter(Facturacion2026.mes.like('2026-%')).all()
        operativos = [fila for fila in registros if not fila.es_next_gen]
        objetivo = round(sum(float(fila.horas_objetivo or 0) for fila in operativos), 2)
        facturadas = round(sum(float(fila.horas_facturadas or 0) for fila in operativos), 2)
        next_gen = round(sum(float(fila.netx_gen or 0) for fila in registros), 2)
        total_facturado = round(sum(float(fila.total_dashboard or 0) for fila in registros), 2)
        assert usuario is not None
        usuario_id = usuario.id
    cliente = app.test_client()
    with cliente.session_transaction() as sesion:
        sesion['usuario_id'] = usuario_id
    resumen = cliente.get('/api/resumen-horas?year=2026').get_json()
    assert resumen['success']
    assert resumen['total']['horas_objetivo'] == objetivo
    assert resumen['total']['horas_facturadas'] == facturadas
    assert resumen['total']['netx_gen_real'] == next_gen
    assert resumen['total']['total_facturado'] == total_facturado
    assert len(resumen['filas']) == 12
    assert len(resumen['trimestres']) == 4
    assert {fila['nombre'] for fila in resumen['grupos']} == {'Personal', 'Santander', 'Multicampaña'}
    assert resumen['gerencias']
    assert resumen['jefaturas']
    assert resumen['detalle_jefaturas']
    assert len(resumen['next_gen']) == 12
    assert round(sum(fila['netx_gen_real'] for fila in resumen['next_gen']), 2) == next_gen
    assert all('nextgen' not in fila['nombre'].replace(' ', '').casefold() for fila in resumen['jefaturas'])
    assert all(len(item['meses']) == 12 and len(item['trimestres']) == 4 for item in resumen['detalle_jefaturas'])
    for campo in ('total_facturado', 'total_obj', 'desvio', 'valor_hora_objetivo', 'valor_hora_promedio',
                  'vh_objetivo_resumen', 'porcentaje_alcance_vh', 'total_desvio', 'porcentaje_desvio', 'variable_real'):
        assert campo in resumen['total']
    for campo in ('participacion_desvio_horas', 'participacion_desvio_variable',
                  'participacion_desvio_penalizaciones', 'otros_real', 'tarifacion_real'):
        assert campo in resumen['total']
    pagina = cliente.get('/resumen-horas')
    assert pagina.status_code == 200
    assert b'>Resumen</h1>' in pagina.data
    kpis = cliente.get('/api/kpis?year=2026&cliente=Gire').get_json()['kpis']
    kpis_anuales = cliente.get('/api/kpis?year=2026').get_json()['kpis']
    assert kpis_anuales['desvio'] == resumen['total']['total_desvio'], (
        kpis_anuales['desvio'], resumen['total']['total_desvio']
    )
    assert kpis_anuales['porcentaje_cumplimiento'] == resumen['total']['porcentaje_cumplimiento']
    with app.app_context():
        gire = Facturacion2026.query.filter_by(mes='2026-08', cliente='Gire').all()
        assert round(kpis['horas_objetivo'], 2) >= round(sum(float(f.horas_objetivo or 0) for f in gire), 2)
        assert round(kpis['horas_facturadas'], 2) >= round(sum(float(f.horas_facturadas or 0) for f in gire), 2)
    print(f"Resumen horas OK: objetivo={objetivo:.2f}; facturadas={facturadas:.2f}")


if __name__ == '__main__':
    verificar()
