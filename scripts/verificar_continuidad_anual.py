"""Open successive future years on an empty test DB, preserving earlier snapshots."""
from pathlib import Path
from datetime import date
from calendar import monthrange
import os
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
folder = ROOT / '.cache' / ('continuidad-anual-' + uuid4().hex)
folder.mkdir(parents=True)
os.environ.update(DATABASE_URL='sqlite:///' + (folder / 'test.db').as_posix(),APP_ENV='development',APP_DEFAULT_YEAR='2026')
from app import create_app
from app.models import db, Usuario, ProyeccionMatriz, ProyeccionPrecio, VariableCampania, FeriadoOperativo
from app.routes import aplicar_calculo_proyeccion

app = create_app()
app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
with app.app_context(), app.test_client() as client:
    admin = Usuario(nombre='Annual fixture',email='annual@example.test',rol='Admin',activo=True,debe_cambiar_password=False,password_hash='not-a-login')
    db.session.add(admin)
    projection = ProyeccionMatriz()
    aplicar_calculo_proyeccion(projection,dict(cliente='Annual fixture',campania='Service',dotacion_requerida=2,carga_semanal='L a V',carga_horaria=8,porcentaje_cumplimiento=100),'2026-01')
    db.session.add(projection)
    db.session.add(ProyeccionPrecio(cliente='Annual fixture',campania='Service',year=2026,mes='2026-01',precio_base=10,precio_final=10,alcance_porcentaje=100))
    db.session.add(VariableCampania(cliente='Annual fixture',campania='Service',year=2026,mes='2026-01',porcentaje=5))
    db.session.add(FeriadoOperativo(year=2026,fecha=date(2026,1,1),nombre='Source-only holiday'))
    db.session.commit()
    with client.session_transaction() as session:
        session['usuario_id'] = admin.id
        session['csrf_token'] = 'annual-fixture-token'
    headers = {'X-CSRF-Token':'annual-fixture-token'}
    def snapshot(year):
        return ([item.to_dict() for item in ProyeccionMatriz.query.filter_by(year=year).order_by(ProyeccionMatriz.id)],
                [item.to_dict() for item in ProyeccionPrecio.query.filter_by(year=year).order_by(ProyeccionPrecio.id)])
    past = {2026:snapshot(2026)}
    for year in (2027,2028,2029):
        response = client.post('/api/matriz-proyecciones/nuevo-anio',json={'year_base':year-1},headers=headers)
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['year_destino'] == year
        rows = ProyeccionMatriz.query.filter_by(year=year).all()
        assert len(rows) == 12 and len({row.mes for row in rows}) == 12
        for row in rows:
            month = int(row.mes[-2:])
            days = sum(date(year,month,day).weekday() < 5 for day in range(1,monthrange(year,month)[1]+1))
            assert row.dias_objetivo == days
            assert row.horas_requeridas == days * 2 * 8
        assert ProyeccionPrecio.query.filter_by(year=year).count() == 12
        assert VariableCampania.query.filter_by(year=year).count() == 12
        assert FeriadoOperativo.query.filter_by(year=year).count() == 0
        for historical_year, values in past.items():
            assert snapshot(historical_year) == values, 'Annual creation changed a past year'
        past[year] = snapshot(year)
        repeat = client.post('/api/matriz-proyecciones/nuevo-anio',json={'year_base':year-1},headers=headers)
        assert repeat.status_code == 409 and snapshot(year) == past[year]
    leap = ProyeccionMatriz.query.filter_by(mes='2028-02').one()
    assert leap.dias_objetivo == 21
    future_price = ProyeccionPrecio(cliente='Annual fixture',campania='Service',year=2030,mes='2030-01',precio_base=99,precio_final=99,alcance_porcentaje=100)
    db.session.add(future_price)
    db.session.add(FeriadoOperativo(year=2030,fecha=date(2030,1,1),nombre='Already configured future holiday'))
    db.session.commit()
    conflict = client.post('/api/matriz-proyecciones/nuevo-anio',json={'year_base':2029},headers=headers)
    assert conflict.status_code == 409
    assert ProyeccionMatriz.query.filter_by(year=2030).count() == 0
    assert db.session.get(ProyeccionPrecio,future_price.id).precio_final == 99
    db.session.delete(future_price)
    db.session.commit()
    opened = client.post('/api/matriz-proyecciones/nuevo-anio',json={'year_base':2029},headers=headers)
    assert opened.status_code == 200 and opened.get_json()['feriados_existentes'] == 1
    assert FeriadoOperativo.query.filter_by(year=2030).count() == 1
    january = ProyeccionMatriz.query.filter_by(mes='2030-01').one()
    business_days = sum(date(2030,1,day).weekday() < 5 for day in range(2,32))
    assert january.dias_objetivo == business_days
    for historical_year,values in past.items():
        assert snapshot(historical_year) == values
    assert client.post('/api/matriz-proyecciones/nuevo-anio',json={'year_base':2100},headers=headers).status_code == 400
print('OK: 2027-2030 creation, leap-year calendar, prices/variables, existing target conflict, holiday preservation, historical preservation and year boundary.')
