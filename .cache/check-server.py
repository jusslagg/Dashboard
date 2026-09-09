import os
from pathlib import Path
import sys
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_COOKIE_SECURE'] = '0'
os.environ['CORS_ORIGINS'] = 'http://127.0.0.1:8010'
from app import create_app, db
from app.models import Usuario, Facturacion2026
app = create_app()
with app.app_context():
    usuario = Usuario(nombre='Prueba dashboard', email='dashboard@example.test', rol='Admin', puesto='Administrador', activo=True, debe_cambiar_password=False)
    usuario.set_password('Prueba123')
    db.session.add(usuario)
    for cliente, objetivo, horas, tarifa in [('Cliente A', 100, 50, 20), ('Cliente B', 10, 20, 2)]:
        db.session.add(Facturacion2026(fecha=date(2026,8,1), mes='2026-08', cliente=cliente, gerente='Gerente prueba', jefe_site='Jefe prueba', campania='Campania', subcampania='Sub', tipo_negocio='Prueba', tipo_jornada='Diurna', horas_objetivo=objetivo, horas_facturadas=horas, valor_hora_objetivo=10, valor_hora=tarifa))
    db.session.commit()
app.run(host='127.0.0.1', port=8010, use_reloader=False)
