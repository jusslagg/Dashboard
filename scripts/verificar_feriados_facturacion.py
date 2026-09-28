"""Comprueba calendario -> jornadas -> horas -> importe y reversión."""
import os
from pathlib import Path
import sys
from datetime import date
from math import isclose

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import FeriadoOperativo, ProyeccionMatriz, ProyeccionPrecio, Usuario
from app.routes import aplicar_calculo_proyeccion, construir_control_proyecciones_data, construir_resumen_proyeccion_data

app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as client:
    user = Usuario(nombre='Prueba', email='feriados@example.test', rol='Admin', puesto='Administrador', activo=True, debe_cambiar_password=False)
    user.set_password('Prueba12345')
    db.session.add(user)
    db.session.add(FeriadoOperativo(year=2026, fecha=date(2026, 11, 23), nombre='Existente', activo=True))
    db.session.flush()
    row = ProyeccionMatriz()
    values = {'cliente': 'Prueba', 'campania': 'Prueba', 'horas_carga_manual': False,
              'porcentaje_cumplimiento': 90, 'jornadas': [
                  {'dotacion_requerida': 10, 'carga_semanal': 'L a V', 'carga_horaria': 6},
                  {'dotacion_requerida': 2, 'carga_semanal': 'S', 'carga_horaria': 4}]}
    aplicar_calculo_proyeccion(row, values, '2026-11')
    assert not row.horas_carga_manual, 'Una matriz general no debe quedar bloqueada como carga PLP'
    db.session.add(row)
    db.session.add(ProyeccionPrecio(cliente='Prueba', campania='Prueba', year=2026, mes='2026-11', precio_base=100, precio_final=100, alcance_porcentaje=100))
    db.session.commit()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'feriados'
    headers = {'X-CSRF-Token': 'feriados'}

    def check(days, hours, saturdays=4):
        db.session.expire_all()
        assert row.jornadas[0].dias_objetivo == days
        assert row.jornadas[0].dotacion_requerida == 10
        assert row.jornadas[1].dotacion_requerida == 2 and row.jornadas[1].dias_objetivo == saturdays
        assert row.dotacion_requerida == 12, 'El feriado no modifica la dotación'
        assert isclose(row.horas_requeridas, hours)
        control = construir_control_proyecciones_data(2026)
        assert isclose(control['total_horas']['meses']['2026-11'], hours * .9)
        data = construir_resumen_proyeccion_data(2026)
        importe = sum(f['meses']['2026-11'] for f in data['filas'] if f['cliente'] == 'Prueba' and f['concepto'] == 'Horas')
        assert isclose(importe, hours * .9 * 100), (importe, hours)
        return importe

    original = check(20, 1232)
    result = client.post('/api/calendario-operativo', headers=headers, json={'fecha': '2026-11-24', 'nombre': 'Nuevo', 'tipo': 'Manual', 'activo': True})
    assert result.status_code == 200, result.json
    holiday = result.json['feriado']['id']
    nuevo = check(19, 1172)
    # Guardar el mismo feriado otra vez no vuelve a descontar horas.
    assert client.post('/api/calendario-operativo', headers=headers, json={'id': holiday, 'fecha': '2026-11-24', 'nombre': 'Nuevo', 'tipo': 'Manual', 'activo': True}).status_code == 200
    check(19, 1172)
    # Desactivar restaura; mover a un sábado afecta sólo la jornada de sábado.
    assert client.post('/api/calendario-operativo', headers=headers, json={'id': holiday, 'fecha': '2026-11-24', 'nombre': 'Nuevo', 'tipo': 'Manual', 'activo': False}).status_code == 200
    check(20, 1232)
    assert client.post('/api/calendario-operativo', headers=headers, json={'id': holiday, 'fecha': '2026-11-28', 'nombre': 'Nuevo', 'tipo': 'Manual', 'activo': True}).status_code == 200
    check(20, 1224, saturdays=3)
    assert client.delete(f'/api/calendario-operativo/{holiday}', headers=headers).status_code == 200
    check(20, 1232)
    print(f'OK: 20 -> 19 días; 1232 -> 1172 horas; facturación {original:.2f} -> {nuevo:.2f}; dotación intacta y reversión sin descuentos repetidos.')
    # Una nueva sincronización no debe volver a congelar las horas del Excel.
    from openpyxl import Workbook
    from scripts.sincronizar_proyectados_excel import sincronizar_matriz
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Matriz'
    sheet.append(['Cabecera']); sheet.append(['Columnas'])
    sheet.append([None, None, 'Importado', 'Importado', 2026, date(2026, 11, 1),
                  'L a V', 20, 6, 10, 1200, 1080, None, None, None, None])
    db.session.add(FeriadoOperativo(year=2026, fecha=date(2026, 11, 24), nombre='Nuevo', activo=True))
    db.session.flush()
    with app.test_request_context('/prueba-importacion'):
        sincronizar_matriz(workbook)
    imported = ProyeccionMatriz.query.filter_by(cliente='Importado', mes='2026-11').one()
    assert not imported.horas_carga_manual and imported.dias_objetivo_manual is None
    assert imported.dotacion_requerida == 10 and imported.dias_objetivo == 19
    assert imported.horas_requeridas == 1140 and isclose(imported.horas_proyectadas, 1026)
    print('OK: las nuevas importaciones mantienen el cálculo por jornadas y el calendario vigente.')
